import datetime
from decimal import Decimal
from django.views.generic import ListView, View
from django.http import HttpResponseRedirect, JsonResponse
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
        return ResourcePlanService.list_plans(
            financial_year_id=int(fy_pk) if fy_pk else None
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.financial_years.models import FinancialYear
        ctx['financial_years'] = FinancialYear.objects.all().order_by('-start_date')
        ctx['active_fy']       = ResourcePlanService.get_active_fy()
        ctx['selected_fy_pk']  = self.request.GET.get('fy', '')

        # For each plan, attach its unmapped project count (3.27)
        plans = ctx['plans']
        for plan in plans:
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
            cd = form.cleaned_data
            # status is hidden on the create form — coerce '' or None to DRAFT
            status = cd.get('status') or ResourcePlan.Status.DRAFT
            # threshold may be None/empty if the field was cleared — default to 10
            threshold = cd.get('allocation_threshold_pct') or Decimal('10.00')

            plan = ResourcePlanService.create_plan({
                'name':                     cd['name'],
                'financial_year_id':        cd['financial_year'].pk,
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
            )
            .order_by('project__programme_name', 'project__project_name')
        )
        unmapped = ResourcePlanService.get_unmapped_projects(plan.pk)
        return {
            'plan':          plan,
            'plan_projects': plan_projects,
            'unmapped':      unmapped,
            'add_project_form': ResourcePlanProjectForm(),
            'add_team_form':    ResourcePlanProjectTeamForm(),
            'add_phase_form':   ResourcePlanPhaseForm(plan=plan),
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
            s1 = GridService.section1_capacity(plan, team, sprints)
            s2 = GridService.section2_allocations(plan, team, sprints)
            s3 = GridService.section3_summary(plan, team, sprints, s1, s2)
            team_grids.append({
                'team':    team,
                'section1': s1,
                'section2': s2,
                'section3': s3,
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
            body = json.loads(request.body)
            days = body.get('days', 0)
            cell = CellService.upsert_cell(
                assignment_id=int(assignment_pk),
                sprint_id=int(sprint_pk),
                days=days,
                changed_by=body.get('changed_by', 'User'),
            )
            return JsonResponse({
                'ok':            True,
                'days':          str(cell.days_allocated),
                'is_auto':       cell.is_auto,
                'assignment_id': assignment_pk,
                'sprint_id':     sprint_pk,
            })
        except (ValidationError, Exception) as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            return JsonResponse({'ok': False, 'detail': msg}, status=400)


# ── Generate placeholder leaves ───────────────────────────

class ResourcePlanGeneratePlaceholdersView(View):
    def post(self, request, pk):
        try:
            plan    = ResourcePlanService.get_plan(pk)
            created = PlaceholderLeaveService.generate_for_plan(plan)
            messages.success(
                request,
                f'{created} placeholder leave row{"s" if created != 1 else ""} generated.'
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse('resource_plan:detail', args=[pk]))