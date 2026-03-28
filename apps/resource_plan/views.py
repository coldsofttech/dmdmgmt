import datetime
from decimal import Decimal
from django.views.generic import ListView, View
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import ValidationError

from .models import (
    ResourcePlan, ResourcePlanProject,
    ResourcePlanProjectTeam, ResourcePlanPhase,
    ResourcePlanAssignment, ResourcePlanConflict,
)
from .services import (
    ResourcePlanService, PlanProjectService,
    PlanProjectTeamService, PlanPhaseService,
    PlanAssignmentService, CellService,
    ConflictService, PlaceholderLeaveService, GridService,
    AutoAllocationEngine, OverflowResolutionService,
    InterimReplacementService, ExportService,
)
from .forms import (
    ResourcePlanForm, ResourcePlanProjectForm,
    ResourcePlanProjectTeamForm, ResourcePlanPhaseForm,
    ResourcePlanAssignmentForm, ResourcePlanCapacityOverrideForm,
)


def _apply_errors(form, exc):
    if hasattr(exc, 'message_dict'):
        for field, errs in exc.message_dict.items():
            for err in errs:
                form.add_error(field if field != '__all__' else None, err)
    elif hasattr(exc, 'message'):
        form.add_error(None, exc.message)
    else:
        form.add_error(None, str(exc))


# ── List ──────────────────────────────────────────────────

class ResourcePlanListView(ListView):
    template_name       = 'resource_plan/plan_list.html'
    context_object_name = 'plans'

    def get_queryset(self):
        fy_pk = self.request.GET.get('fy', '').strip()
        q     = self.request.GET.get('q',  '').strip()
        qs    = ResourcePlanService.list_plans(
            financial_year_id=int(fy_pk) if fy_pk else None,
            search=q or None,
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.financial_years.models import FinancialYear
        ctx['financial_years'] = FinancialYear.objects.all().order_by('-start_date')
        ctx['active_fy']       = ResourcePlanService.get_active_fy()
        ctx['selected_fy_pk']  = self.request.GET.get('fy', '')
        ctx['search_q']        = self.request.GET.get('q', '')

        # Attach unmapped project count to each plan
        for plan in ctx['plans']:
            plan.unmapped_count = len(ResourcePlanService.get_unmapped_projects(plan.pk))
        return ctx


# ── Create ────────────────────────────────────────────────

class ResourcePlanCreateView(View):
    template_name = 'resource_plan/plan_form.html'

    def get(self, request):
        active_fy = ResourcePlanService.get_active_fy()
        form = ResourcePlanForm(initial={'financial_year': active_fy} if active_fy else {})
        return render(request, self.template_name, {
            'form': form, 'is_create': True
        })

    def post(self, request):
        form = ResourcePlanForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form, 'is_create': True
            })
        try:
            cd   = form.cleaned_data
            status    = cd.get('status') or ResourcePlan.Status.DRAFT
            threshold = cd.get('allocation_threshold_pct') or Decimal('10.00')
            plan = ResourcePlanService.create_plan({
                'name':                     cd['name'],
                'financial_year_id':        cd['financial_year'].pk,
                # 'status':                   cd.get('status', ResourcePlan.Status.DRAFT),
                # 'allocation_threshold_pct': cd.get('allocation_threshold_pct', Decimal('10.00')),
                'status':                   status,
                'allocation_threshold_pct': threshold,
                'scope_notes':              cd.get('scope_notes', ''),
            })
            messages.success(request, f'Resource plan "{plan.name}" created.')
            return HttpResponseRedirect(
                reverse('resource_plan:configure', args=[plan.pk])
            )
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {
                'form': form, 'is_create': True
            })


# ── Update ────────────────────────────────────────────────

class ResourcePlanUpdateView(View):
    template_name = 'resource_plan/plan_form.html'

    def get(self, request, pk):
        plan = ResourcePlanService.get_plan(pk)
        form = ResourcePlanForm(instance=plan)
        return render(request, self.template_name, {
            'form': form, 'plan': plan, 'is_create': False
        })

    def post(self, request, pk):
        plan = ResourcePlanService.get_plan(pk)
        form = ResourcePlanForm(request.POST, instance=plan)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form, 'plan': plan, 'is_create': False
            })
        try:
            cd      = form.cleaned_data
            updated = ResourcePlanService.update_plan(pk, {
                'name':                     cd['name'],
                'status':                   cd.get('status'),
                'allocation_threshold_pct': cd.get('allocation_threshold_pct'),
                'scope_notes':              cd.get('scope_notes', ''),
            })
            messages.success(request, f'"{updated.name}" updated.')
            return HttpResponseRedirect(reverse('resource_plan:detail', args=[pk]))
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {
                'form': form, 'plan': plan, 'is_create': False
            })


# ── Configure (wizard step 2) ─────────────────────────────

class ResourcePlanConfigureView(View):
    """
    The configuration wizard: scopes projects into the plan, assigns teams,
    adds phases, and creates assignments (engineer mapping).
    Phase 1 renders a multi-section form for adding projects/teams/phases.
    """
    template_name = 'resource_plan/plan_configure.html'

    def _ctx(self, plan):
        from apps.financial_years.models import FinancialYear
        plan_projects = (
            ResourcePlanProject.objects
            .filter(plan=plan)
            .select_related('project')
            .prefetch_related(
                'project_teams__team',
                'project_teams__phases__assignments__team_member',
                'sprint_budgets__sprint',   # ← Round B: per-sprint budget rows
            )
            .order_by('project__programme_name', 'project__project_name')
        )
        unmapped = ResourcePlanService.get_unmapped_projects(plan.pk)
        from .forms import ResourcePlanSprintBudgetForm
        return {
            'plan':               plan,
            'plan_projects':      plan_projects,
            'unmapped':           unmapped,
            'add_project_form':   ResourcePlanProjectForm(),
            'add_team_form':      ResourcePlanProjectTeamForm(),
            'add_phase_form':     ResourcePlanPhaseForm(plan=plan),
            'sprint_budget_form': ResourcePlanSprintBudgetForm(plan=plan),
        }

    def get(self, request, pk):
        plan = ResourcePlanService.get_plan(pk)
        return render(request, self.template_name, self._ctx(plan))

    def post(self, request, pk):
        """Handle sub-forms via action param."""
        plan   = ResourcePlanService.get_plan(pk)
        action = request.POST.get('_action', '')

        if action == 'add_project':
            return self._add_project(request, plan)
        if action == 'remove_project':
            return self._remove_project(request, plan)
        if action == 'add_team':
            return self._add_team(request, plan)
        if action == 'add_phase':
            return self._add_phase(request, plan)
        if action == 'add_sprint_budget':
            return self._add_sprint_budget(request, plan)
        if action == 'delete_sprint_budget':
            return self._delete_sprint_budget(request, plan)

        messages.error(request, 'Unknown action.')
        return HttpResponseRedirect(reverse('resource_plan:configure', args=[pk]))

    def _add_project(self, request, plan):
        form = ResourcePlanProjectForm(request.POST)
        if not form.is_valid():
            ctx = self._ctx(plan)
            ctx['add_project_form'] = form
            return render(request, self.template_name, ctx)
        try:
            cd = form.cleaned_data
            PlanProjectService.create(plan.pk, {
                'project_id':          cd['project'].pk,
                'basis':               cd['basis'],
                'custom_amount':       cd.get('custom_amount'),
                'priority_override':   cd.get('priority_override', ''),
                'confidence_override': cd.get('confidence_override', ''),
                'dates_strict':        cd.get('dates_strict', False),
                'notes':               cd.get('notes', ''),
            })
            messages.success(request, f'Project "{cd["project"].display_name}" added to plan.')
        except ValidationError as exc:
            _apply_errors(form, exc)
            ctx = self._ctx(plan)
            ctx['add_project_form'] = form
            return render(request, self.template_name, ctx)
        return HttpResponseRedirect(reverse('resource_plan:configure', args=[plan.pk]))

    def _remove_project(self, request, plan):
        pp_pk = request.POST.get('plan_project_pk', '').strip()
        if pp_pk:
            try:
                PlanProjectService.delete(int(pp_pk))
                messages.success(request, 'Project removed from plan.')
            except Exception as exc:
                messages.error(request, str(exc))
        return HttpResponseRedirect(reverse('resource_plan:configure', args=[plan.pk]))

    def _add_team(self, request, plan):
        pp_pk = request.POST.get('plan_project_pk', '').strip()
        if not pp_pk:
            messages.error(request, 'Plan project is required.')
            return HttpResponseRedirect(reverse('resource_plan:configure', args=[plan.pk]))
        form = ResourcePlanProjectTeamForm(request.POST)
        if not form.is_valid():
            ctx = self._ctx(plan)
            ctx['add_team_form'] = form
            return render(request, self.template_name, ctx)
        try:
            cd = form.cleaned_data
            PlanProjectTeamService.create(int(pp_pk), {
                'team_id':         cd['team'].pk,
                'allocation_type': cd['allocation_type'],
                'allocation_value': cd['allocation_value'],
                'sequence_order':  cd['sequence_order'],
                'notes':           cd.get('notes', ''),
            })
            messages.success(request, f'Team "{cd["team"].name}" assigned.')
        except ValidationError as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse('resource_plan:configure', args=[plan.pk]))

    def _add_phase(self, request, plan):
        ppt_pk = request.POST.get('plan_project_team_pk', '').strip()
        if not ppt_pk:
            messages.error(request, 'Project-team is required.')
            return HttpResponseRedirect(reverse('resource_plan:configure', args=[plan.pk]))
        form = ResourcePlanPhaseForm(request.POST, plan=plan)
        if not form.is_valid():
            ctx = self._ctx(plan)
            ctx['add_phase_form'] = form
            return render(request, self.template_name, ctx)
        try:
            cd = form.cleaned_data
            PlanPhaseService.create(int(ppt_pk), {
                'name':                 cd['name'],
                'sequence_order':       cd['sequence_order'],
                'start_sprint_id':      cd['start_sprint'].pk if cd.get('start_sprint') else None,
                'end_sprint_id':        cd['end_sprint'].pk   if cd.get('end_sprint')   else None,
                'predecessor_phase_id': cd['predecessor_phase'].pk if cd.get('predecessor_phase') else None,
                'dependency_type':      cd.get('dependency_type', ''),
                'ramp_pattern':         cd['ramp_pattern'],
                'max_days_per_sprint':  cd.get('max_days_per_sprint'),
                'notes':                cd.get('notes', ''),
            })
            messages.success(request, f'Phase "{cd["name"]}" added.')
        except ValidationError as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse('resource_plan:configure', args=[plan.pk]))


    def _add_sprint_budget(self, request, plan):
        """Add or update a per-sprint budget release for a plan-project."""
        from .models import ResourcePlanSprintBudget
        from .forms import ResourcePlanSprintBudgetForm
        pp_pk = request.POST.get('plan_project_pk', '').strip()
        if not pp_pk:
            messages.error(request, 'Project is required for sprint budget.')
            return HttpResponseRedirect(reverse('resource_plan:configure', args=[plan.pk]))
        form = ResourcePlanSprintBudgetForm(request.POST, plan=plan)
        if not form.is_valid():
            messages.error(request, f'Sprint budget error: {form.errors}')
            return HttpResponseRedirect(reverse('resource_plan:configure', args=[plan.pk]))
        try:
            cd = form.cleaned_data
            obj, created = ResourcePlanSprintBudget.objects.update_or_create(
                plan_project_id=int(pp_pk),
                sprint=cd['sprint'],
                defaults={
                    'budget_amount': cd['budget_amount'],
                    'notes':         cd.get('notes', ''),
                },
            )
            messages.success(
                request,
                f'Sprint budget {"created" if created else "updated"} for {cd["sprint"].name}.'
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse('resource_plan:configure', args=[plan.pk]))

    def _delete_sprint_budget(self, request, plan):
        from .models import ResourcePlanSprintBudget
        sb_pk = request.POST.get('sprint_budget_pk', '').strip()
        if sb_pk:
            try:
                ResourcePlanSprintBudget.objects.filter(
                    pk=int(sb_pk),
                    plan_project__plan=plan,
                ).delete()
                messages.success(request, 'Sprint budget removed.')
            except Exception as exc:
                messages.error(request, str(exc))
        return HttpResponseRedirect(reverse('resource_plan:configure', args=[plan.pk]))


# ── Detail (grid view) ────────────────────────────────────

class ResourcePlanDetailView(View):
    template_name = 'resource_plan/plan_detail.html'

    def get(self, request, pk):
        plan    = ResourcePlanService.get_plan(pk)
        sprints = GridService.get_sprints_for_plan(plan)
        today   = datetime.date.today()

        # Get all active teams involved in this plan
        from apps.teams.models import Team
        team_pks = list(
            ResourcePlanProjectTeam.objects.filter(
                plan_project__plan=plan
            ).values_list('team_id', flat=True).distinct()
        )
        teams = list(Team.objects.filter(pk__in=team_pks, is_active=True).order_by('name'))

        # Build grid data for each team
        team_grids = []
        for team in teams:
            s1   = GridService.section1_capacity(plan, team, sprints)
            s1_5 = GridService.section1_5_leaves(plan, team, sprints)
            s2   = GridService.section2_allocations(plan, team, sprints)
            s3   = GridService.section3_summary(plan, team, sprints, s1, s2)
            team_grids.append({
                'team':      team,
                'section1':  s1,
                'section1_5': s1_5,
                'section2':  s2,
                'section3':  s3,
            })

        # Pending conflicts
        conflicts = ConflictService.get_pending_conflicts(pk)

        # Unmapped projects (3.27)
        unmapped = ResourcePlanService.get_unmapped_projects(pk)

        ctx = {
            'plan':       plan,
            'sprints':    sprints,
            'teams':      teams,
            'team_grids': team_grids,
            'conflicts':  conflicts,
            'unmapped':   unmapped,
            'today':      today,
        }
        return render(request, self.template_name, ctx)


# ── Delete ────────────────────────────────────────────────

class ResourcePlanDeleteView(View):
    def post(self, request, pk):
        try:
            plan = ResourcePlanService.get_plan(pk)
            name = plan.name
            ResourcePlanService.delete_plan(pk)
            return JsonResponse({'ok': True, 'name': name})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


# ── Cell AJAX update ──────────────────────────────────────

class ResourcePlanCellUpdateView(View):
    """POST /resource-plan/<plan_pk>/cell/<assignment_pk>/<sprint_pk>/"""

    def post(self, request, plan_pk, assignment_pk, sprint_pk):
        import json
        try:
            # Block edits when plan is LOCKED
            plan = ResourcePlanService.get_plan(plan_pk)
            if plan.status == ResourcePlan.Status.LOCKED:
                return JsonResponse(
                    {'ok': False, 'detail': 'This plan is locked. Change status to edit.'},
                    status=403,
                )
            body = json.loads(request.body)
            days = body.get('days', 0)

            cell, ctx = CellService.upsert_cell(
                assignment_id=int(assignment_pk),
                sprint_id=int(sprint_pk),
                days=days,
                changed_by=body.get('changed_by', 'User'),
            )
            return JsonResponse({
                'ok':                   True,
                'days':                 str(cell.days_allocated),
                'is_auto':              cell.is_auto,
                'assignment_id':        assignment_pk,
                'sprint_id':            sprint_pk,
                # Phase 2 enriched payload
                'sprint_total':         str(ctx['sprint_total_allocated']),
                'member_remaining':     str(ctx['member_remaining']),
                'conflict_count':       ctx['conflict_count'],
                'new_conflicts':        ctx['new_conflicts'],
                'unmapped_count':       ctx['unmapped_count'],
            })
        except (ValidationError, Exception) as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            return JsonResponse({'ok': False, 'detail': msg}, status=400)


# ── Generate placeholder leaves ───────────────────────────

class ResourcePlanGeneratePlaceholdersView(View):
    def post(self, request, pk):
        try:
            plan   = ResourcePlanService.get_plan(pk)
            result = PlaceholderLeaveService.generate_for_plan(plan)
            created = result.get('created', 0)
            deleted = result.get('deleted', 0)
            members = result.get('members', [])

            summary_parts = [
                f'{created} placeholder row{"s" if created != 1 else ""} created'
            ]
            if deleted:
                summary_parts.append(f'{deleted} old row{"s" if deleted != 1 else ""} replaced')
            if members:
                names = ', '.join(m['name'] for m in members[:4])
                if len(members) > 4:
                    names += f' + {len(members) - 4} more'
                summary_parts.append(f'for: {names}')

            messages.success(request, ' — '.join(summary_parts) + '.')
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse('resource_plan:detail', args=[pk]))


# ═══════════════════════════════════════════════════════════
#  Round A — Project configuration screen (2.11 / 2.12)
# ═══════════════════════════════════════════════════════════

class ResourcePlanProjectsView(View):
    """
    /resource-plan/<pk>/projects/
    Separate table screen listing all scoped projects with their teams,
    phases, and assignment counts. View / edit / delete per row.
    """
    template_name = 'resource_plan/plan_projects.html'

    def get(self, request, pk):
        plan = ResourcePlanService.get_plan(pk)
        plan_projects = (
            ResourcePlanProject.objects
            .filter(plan=plan)
            .select_related('project')
            .prefetch_related(
                'project_teams__team',
                'project_teams__phases__assignments__team_member',
            )
            .order_by('project__programme_name', 'project__project_name')
        )
        return render(request, self.template_name, {
            'plan':          plan,
            'plan_projects': plan_projects,
        })


class ResourcePlanProjectEditView(View):
    """
    /resource-plan/<plan_pk>/projects/<pp_pk>/edit/
    Edit one plan-project (basis, priority override, confidence override,
    dates_strict, notes).
    """
    template_name = 'resource_plan/plan_project_edit.html'

    def _get(self, plan, pp):
        from .forms import ResourcePlanProjectForm
        form = ResourcePlanProjectForm(instance=pp)
        return render(self.request, self.template_name, {
            'plan': plan, 'pp': pp, 'form': form
        })

    def get(self, request, plan_pk, pp_pk):
        self.request = request
        plan = ResourcePlanService.get_plan(plan_pk)
        pp   = ResourcePlanProject.objects.select_related('project').get(pk=pp_pk, plan=plan)
        return self._get(plan, pp)

    def post(self, request, plan_pk, pp_pk):
        plan = ResourcePlanService.get_plan(plan_pk)
        pp   = ResourcePlanProject.objects.select_related('project').get(pk=pp_pk, plan=plan)
        from .forms import ResourcePlanProjectForm
        form = ResourcePlanProjectForm(request.POST, instance=pp)
        if not form.is_valid():
            return render(request, self.template_name, {
                'plan': plan, 'pp': pp, 'form': form
            })
        try:
            cd = form.cleaned_data
            PlanProjectService.update(pp.pk, {
                'basis':               cd['basis'],
                'custom_amount':       cd.get('custom_amount'),
                'priority_override':   cd.get('priority_override', ''),
                'confidence_override': cd.get('confidence_override', ''),
                'dates_strict':        cd.get('dates_strict', False),
                'notes':               cd.get('notes', ''),
            })
            messages.success(request, f'"{pp.project.display_name}" updated.')
            return HttpResponseRedirect(
                reverse('resource_plan:projects', args=[plan_pk])
            )
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {
                'plan': plan, 'pp': pp, 'form': form
            })


class ResourcePlanProjectDeleteView(View):
    """POST /resource-plan/<plan_pk>/projects/<pp_pk>/delete/ → JSON"""

    def post(self, request, plan_pk, pp_pk):
        try:
            PlanProjectService.delete(pp_pk)
            return JsonResponse({'ok': True})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


# ═══════════════════════════════════════════════════════════
#  Round A — Phase CRUD (real modal backing views)
# ═══════════════════════════════════════════════════════════

class ResourcePlanPhaseEditView(View):
    """
    GET/POST /resource-plan/<plan_pk>/phases/<phase_pk>/edit/
    Returns JSON fragment for modal rendering.
    """

    def get(self, request, plan_pk, phase_pk):
        plan  = ResourcePlanService.get_plan(plan_pk)
        phase = ResourcePlanPhase.objects.select_related(
            'plan_project_team__plan_project__project',
            'plan_project_team__team',
        ).get(pk=phase_pk)
        from .forms import ResourcePlanPhaseForm
        form = ResourcePlanPhaseForm(instance=phase, plan=plan)
        return render(request, 'resource_plan/phase_form_modal.html', {
            'plan': plan, 'phase': phase, 'form': form,
            'is_create': False,
        })

    def post(self, request, plan_pk, phase_pk):
        plan  = ResourcePlanService.get_plan(plan_pk)
        phase = ResourcePlanPhase.objects.get(pk=phase_pk)
        from .forms import ResourcePlanPhaseForm
        form = ResourcePlanPhaseForm(request.POST, instance=phase, plan=plan)
        if not form.is_valid():
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        try:
            cd = form.cleaned_data
            PlanPhaseService.update(phase_pk, {
                'name':                 cd['name'],
                'sequence_order':       cd['sequence_order'],
                'start_sprint_id':      cd['start_sprint'].pk if cd.get('start_sprint') else None,
                'end_sprint_id':        cd['end_sprint'].pk   if cd.get('end_sprint')   else None,
                'predecessor_phase_id': cd['predecessor_phase'].pk if cd.get('predecessor_phase') else None,
                'dependency_type':      cd.get('dependency_type', ''),
                'ramp_pattern':         cd['ramp_pattern'],
                'max_days_per_sprint':  cd.get('max_days_per_sprint'),
                'notes':                cd.get('notes', ''),
            })
            return JsonResponse({'ok': True})
        except ValidationError as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            return JsonResponse({'ok': False, 'detail': msg}, status=400)


class ResourcePlanPhaseDeleteView(View):
    def post(self, request, plan_pk, phase_pk):
        try:
            PlanPhaseService.delete(phase_pk)
            return JsonResponse({'ok': True})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


# ═══════════════════════════════════════════════════════════
#  Round A — Assignment CRUD (2.3 / 2.4 / 2.17)
# ═══════════════════════════════════════════════════════════

class ResourcePlanAssignmentListView(View):
    """
    GET /resource-plan/<plan_pk>/phases/<phase_pk>/assignments/
    Returns a JSON list of assignments for a phase — used to refresh
    the assignment table in the configure modal without page reload.
    """

    def get(self, request, plan_pk, phase_pk):
        assignments = (
            ResourcePlanAssignment.objects
            .filter(phase_id=phase_pk)
            .select_related('team_member', 'phase__plan_project_team__team')
            .order_by('team_member__last_name', 'placeholder_name')
        )
        data = [
            {
                'id':              a.pk,
                'display_name':    a.display_name,
                'assignment_type': a.assignment_type,
                'is_interim':      a.is_interim,
                'pause_from':      a.pause_from_sprint.name if a.pause_from_sprint else None,
                'resume_at':       a.resume_at_sprint.name  if a.resume_at_sprint  else None,
                'notes':           a.notes,
            }
            for a in assignments
        ]
        return JsonResponse({'ok': True, 'assignments': data})


class ResourcePlanAssignmentCreateView(View):
    """
    GET  /resource-plan/<plan_pk>/phases/<phase_pk>/assignments/new/
         Returns the assignment form as an HTML fragment (for modal).
    POST /resource-plan/<plan_pk>/phases/<phase_pk>/assignments/new/
         Creates the assignment. Returns JSON {ok, id, display_name}.
    """

    def _get_team(self, phase_pk):
        try:
            return ResourcePlanPhase.objects.select_related(
                'plan_project_team__team'
            ).get(pk=phase_pk).plan_project_team.team
        except Exception:
            return None

    def get(self, request, plan_pk, phase_pk):
        plan = ResourcePlanService.get_plan(plan_pk)
        team = self._get_team(phase_pk)
        from .forms import ResourcePlanAssignmentForm
        form = ResourcePlanAssignmentForm(team=team, plan=plan)
        return render(request, 'resource_plan/assignment_form_modal.html', {
            'plan':      plan,
            'phase_pk':  phase_pk,
            'form':      form,
            'is_create': True,
            'team':      team,
        })

    def post(self, request, plan_pk, phase_pk):
        plan = ResourcePlanService.get_plan(plan_pk)
        team = self._get_team(phase_pk)
        from .forms import ResourcePlanAssignmentForm
        form = ResourcePlanAssignmentForm(request.POST, team=team, plan=plan)
        if not form.is_valid():
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        try:
            cd = form.cleaned_data
            a  = PlanAssignmentService.create(int(phase_pk), {
                'team_member_id':       cd['team_member'].pk if cd.get('team_member') else None,
                'placeholder_name':     cd.get('placeholder_name', ''),
                'assignment_type':      cd['assignment_type'],
                'is_interim':           cd.get('is_interim', False),
                'replaces_assignment_id': cd['replaces_assignment'].pk
                                          if cd.get('replaces_assignment') else None,
                'pause_from_sprint_id': cd['pause_from_sprint'].pk
                                        if cd.get('pause_from_sprint') else None,
                'resume_at_sprint_id':  cd['resume_at_sprint'].pk
                                        if cd.get('resume_at_sprint') else None,
                'notes':                cd.get('notes', ''),
            })
            return JsonResponse({
                'ok':           True,
                'id':           a.pk,
                'display_name': a.display_name,
                'type':         a.assignment_type,
            })
        except ValidationError as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            return JsonResponse({'ok': False, 'detail': msg}, status=400)


class ResourcePlanAssignmentEditView(View):
    """
    GET  /resource-plan/<plan_pk>/assignments/<assignment_pk>/edit/
    POST /resource-plan/<plan_pk>/assignments/<assignment_pk>/edit/
    """

    def _get_objects(self, plan_pk, assignment_pk):
        plan = ResourcePlanService.get_plan(plan_pk)
        a    = ResourcePlanAssignment.objects.select_related(
            'team_member',
            'phase__plan_project_team__team',
        ).get(pk=assignment_pk)
        return plan, a

    def get(self, request, plan_pk, assignment_pk):
        plan, a = self._get_objects(plan_pk, assignment_pk)
        from .forms import ResourcePlanAssignmentForm
        team = a.phase.plan_project_team.team
        form = ResourcePlanAssignmentForm(instance=a, team=team, plan=plan)
        return render(request, 'resource_plan/assignment_form_modal.html', {
            'plan':           plan,
            'phase_pk':       a.phase_id,
            'form':           form,
            'is_create':      False,
            'assignment':     a,
            'team':           team,
        })

    def post(self, request, plan_pk, assignment_pk):
        plan, a = self._get_objects(plan_pk, assignment_pk)
        team    = a.phase.plan_project_team.team
        from .forms import ResourcePlanAssignmentForm
        form = ResourcePlanAssignmentForm(request.POST, instance=a, team=team, plan=plan)
        if not form.is_valid():
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        try:
            cd      = form.cleaned_data
            updated = PlanAssignmentService.update(assignment_pk, {
                'team_member_id':       cd['team_member'].pk if cd.get('team_member') else None,
                'placeholder_name':     cd.get('placeholder_name', ''),
                'assignment_type':      cd['assignment_type'],
                'is_interim':           cd.get('is_interim', False),
                'replaces_assignment_id': cd['replaces_assignment'].pk
                                          if cd.get('replaces_assignment') else None,
                'pause_from_sprint_id': cd['pause_from_sprint'].pk
                                        if cd.get('pause_from_sprint') else None,
                'resume_at_sprint_id':  cd['resume_at_sprint'].pk
                                        if cd.get('resume_at_sprint') else None,
                'notes':                cd.get('notes', ''),
            })
            return JsonResponse({'ok': True, 'display_name': updated.display_name})
        except ValidationError as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            return JsonResponse({'ok': False, 'detail': msg}, status=400)


class ResourcePlanAssignmentDeleteView(View):
    def post(self, request, plan_pk, assignment_pk):
        try:
            PlanAssignmentService.delete(assignment_pk)
            return JsonResponse({'ok': True})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


# ═══════════════════════════════════════════════════════════
#  Round A — Placeholder leave view / edit (2.22)
# ═══════════════════════════════════════════════════════════

class ResourcePlanPlaceholdersView(View):
    """
    GET  /resource-plan/<pk>/placeholders/
    Shows all ResourcePlanLeafPlaceholder rows for this plan,
    grouped by team member, with edit and delete per row.
    Also allows manual addition of placeholder rows.
    """
    template_name = 'resource_plan/plan_placeholders.html'

    def get(self, request, pk):
        plan = ResourcePlanService.get_plan(pk)
        from .models import ResourcePlanLeafPlaceholder
        from apps.sprints.models import Sprint

        placeholders = (
            ResourcePlanLeafPlaceholder.objects
            .filter(plan=plan)
            .select_related('team_member', 'sprint')
            .order_by('team_member__last_name', 'team_member__first_name', 'sprint__start_date')
        )

        # Group by member for accordion display
        from collections import OrderedDict
        grouped = OrderedDict()
        for ph in placeholders:
            key = ph.team_member_id
            if key not in grouped:
                grouped[key] = {'member': ph.team_member, 'rows': [], 'total_days': 0}
            grouped[key]['rows'].append(ph)
            grouped[key]['total_days'] += float(ph.days)

        sprints = Sprint.objects.filter(
            financial_year=plan.financial_year
        ).order_by('start_date')

        return render(request, self.template_name, {
            'plan':     plan,
            'grouped':  list(grouped.values()),
            'sprints':  sprints,
            'total_ph': placeholders.count(),
        })


class ResourcePlanPlaceholderUpdateView(View):
    """
    POST /resource-plan/<plan_pk>/placeholders/<ph_pk>/update/
    Body: { "days": 0.5 | 1.0 }   Returns JSON.
    """

    def post(self, request, plan_pk, ph_pk):
        import json
        from .models import ResourcePlanLeafPlaceholder
        try:
            body = json.loads(request.body)
            days = body.get('days')
            if days not in (0.5, 1.0):
                return JsonResponse(
                    {'ok': False, 'detail': 'Days must be 0.5 or 1.0.'},
                    status=400,
                )
            from decimal import Decimal
            ph      = ResourcePlanLeafPlaceholder.objects.get(pk=ph_pk, plan_id=plan_pk)
            ph.days = Decimal(str(days))
            ph.is_auto_generated = False  # now manually set
            ph.save()
            return JsonResponse({'ok': True, 'days': str(ph.days)})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


class ResourcePlanPlaceholderDeleteView(View):
    """POST /resource-plan/<plan_pk>/placeholders/<ph_pk>/delete/"""

    def post(self, request, plan_pk, ph_pk):
        from .models import ResourcePlanLeafPlaceholder
        try:
            ResourcePlanLeafPlaceholder.objects.get(pk=ph_pk, plan_id=plan_pk).delete()
            return JsonResponse({'ok': True})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


class ResourcePlanPlaceholderCreateView(View):
    """
    POST /resource-plan/<plan_pk>/placeholders/new/
    Body: { "team_member_id": N, "sprint_id": N, "days": 0.5|1.0 }
    """

    def post(self, request, plan_pk):
        import json
        from .models import ResourcePlanLeafPlaceholder
        from decimal import Decimal
        try:
            body      = json.loads(request.body)
            member_id = body.get('team_member_id')
            sprint_id = body.get('sprint_id')
            days      = body.get('days', 1.0)
            if days not in (0.5, 1.0):
                return JsonResponse({'ok': False, 'detail': 'Days must be 0.5 or 1.0.'}, status=400)
            ph, created = ResourcePlanLeafPlaceholder.objects.get_or_create(
                plan_id=plan_pk,
                team_member_id=member_id,
                sprint_id=sprint_id,
                defaults={
                    'days': Decimal(str(days)),
                    'is_auto_generated': False,
                },
            )
            if not created:
                ph.days = Decimal(str(days))
                ph.is_auto_generated = False
                ph.save()
            return JsonResponse({'ok': True, 'id': ph.pk, 'days': str(ph.days), 'created': created})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


# ═══════════════════════════════════════════════════════════
#  Phase 3 — Auto-allocation engine view
# ═══════════════════════════════════════════════════════════

class ResourcePlanRunEngineView(View):
    """
    POST /resource-plan/<pk>/run-engine/
    Body: { "dry_run": true|false }
    Runs AutoAllocationEngine and returns a JSON summary.
    """

    def post(self, request, pk):
        import json
        try:
            plan = ResourcePlanService.get_plan(pk)
            if plan.status == ResourcePlan.Status.LOCKED:
                return JsonResponse(
                    {'ok': False, 'detail': 'Plan is locked.'},
                    status=403,
                )
            body    = json.loads(request.body) if request.body else {}
            dry_run = bool(body.get('dry_run', False))
            result  = AutoAllocationEngine.run(plan_id=pk, dry_run=dry_run)
            if not dry_run:
                messages.success(
                    request,
                    f'Auto-allocation complete: {result.cells_written} cells written, '
                    f'{result.conflicts_raised} conflicts raised.',
                )
            return JsonResponse({
                'ok':      True,
                'dry_run': dry_run,
                **result.to_dict(),
            })
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


# ═══════════════════════════════════════════════════════════
#  Phase 3 — Conflict resolution view
# ═══════════════════════════════════════════════════════════

class ResourcePlanResolveConflictView(View):
    """
    POST /resource-plan/<plan_pk>/conflicts/<conflict_pk>/resolve/
    Body: {
      "resolution": "PUSHED_RIGHT"|"SPLIT"|"REPLACED"|"PLACEHOLDER"|
                    "DEPRIORITISED"|"DISMISSED",
      "sprint_offset":      int       (PUSHED_RIGHT),
      "split_days":         "5.0"     (SPLIT),
      "new_member_id":      int       (REPLACED),
      "placeholder_name":   str       (PLACEHOLDER),
    }
    """

    def post(self, request, plan_pk, conflict_pk):
        import json
        try:
            body       = json.loads(request.body) if request.body else {}
            resolution = body.get('resolution', '').strip()
            if not resolution:
                return JsonResponse(
                    {'ok': False, 'detail': '"resolution" is required.'},
                    status=400,
                )
            extra = {
                'sprint_offset':    int(body['sprint_offset'])  if 'sprint_offset'    in body else 1,
                'split_days':       body.get('split_days', '0'),
                'new_member_id':    body.get('new_member_id'),
                'placeholder_name': body.get('placeholder_name', 'ENGINEER TBC'),
            }
            conflict = OverflowResolutionService.apply_resolution(
                conflict_id=int(conflict_pk),
                resolution=resolution,
                extra=extra,
            )
            # Return updated pending conflict count
            pending = ResourcePlanConflict.objects.filter(
                plan_id=plan_pk,
                resolution=ResourcePlanConflict.Resolution.PENDING,
            ).count()
            return JsonResponse({
                'ok':            True,
                'conflict_id':   conflict.pk,
                'resolution':    conflict.resolution,
                'pending_count': pending,
            })
        except (ValidationError, Exception) as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            return JsonResponse({'ok': False, 'detail': msg}, status=400)


# ═══════════════════════════════════════════════════════════
#  Phase 3 — Interim replacement view
# ═══════════════════════════════════════════════════════════

class ResourcePlanInterimView(View):
    """
    POST /resource-plan/<plan_pk>/assignments/<assignment_pk>/interim/
    Body: { "new_member_id": int, "sprint_id": int (optional) }
    Creates an interim assignment covering the given engineer's absence.
    """

    def post(self, request, plan_pk, assignment_pk):
        import json
        try:
            body          = json.loads(request.body) if request.body else {}
            new_member_id = body.get('new_member_id')
            sprint_id     = body.get('sprint_id')
            if not new_member_id:
                return JsonResponse(
                    {'ok': False, 'detail': '"new_member_id" is required.'},
                    status=400,
                )
            plan     = ResourcePlanService.get_plan(plan_pk)
            original = ResourcePlanAssignment.objects.select_related(
                'phase', 'team_member'
            ).get(pk=assignment_pk)

            sprint = None
            if sprint_id:
                from apps.sprints.models import Sprint
                sprint = Sprint.objects.get(pk=sprint_id)

            interim = InterimReplacementService.create_interim(
                phase_id               = original.phase_id,
                replaces_assignment_id = original.pk,
                team_member_id         = int(new_member_id),
                plan                   = plan,
                sprint                 = sprint,
            )
            return JsonResponse({
                'ok':            True,
                'interim_id':    interim.pk,
                'interim_name':  interim.display_name,
                'original_name': original.display_name,
            })
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


# ═══════════════════════════════════════════════════════════
#  Phase 3 — Export view
# ═══════════════════════════════════════════════════════════

class ResourcePlanExportView(View):
    """
    GET /resource-plan/<pk>/export/
    Streams the plan as an .xlsx file download.
    """

    def get(self, request, pk):
        try:
            plan = ResourcePlanService.get_plan(pk)
            buf  = ExportService.export_plan_xlsx(plan_id=pk)
            filename = (
                f'resource_plan_{plan.financial_year.short_fy}_'
                f'{plan.name.replace(" ", "_")}.xlsx'
            )
            response = HttpResponse(
                buf.read(),
                content_type=(
                    'application/vnd.openxmlformats-officedocument'
                    '.spreadsheetml.sheet'
                ),
            )
            response['Content-Disposition'] = (
                f'attachment; filename="{filename}"'
            )
            return response
        except Exception as exc:
            messages.error(request, f'Export failed: {exc}')
            return HttpResponseRedirect(
                reverse('resource_plan:detail', args=[pk])
            )