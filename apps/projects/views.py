from django.views.generic import ListView, DetailView, View
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import ValidationError

from .services import ProjectService
from .forms import ProjectForm, ProjectCommentForm
from .models import Project, ProjectComment

def _form_to_service_data(cd: dict) -> dict:
    collaborators_qs = cd.get('collaborators') or []
    return {
        'programme_name':                cd.get('programme_name', ''),
        'project_name':                  cd['project_name'],
        'display_name':                  cd.get('display_name', ''),
        'project_code':                  cd.get('project_code', ''),
        'project_type':                  cd.get('project_type', 'Project'),
        'label':                         cd.get('label') or None,
        'project_contacts':              cd.get('project_contacts', ''),
        'finance_contacts':              cd.get('finance_contacts', ''),
        'assigned_team_id':              cd['assigned_team'].pk if cd.get('assigned_team') else None,
        'collaborator_ids':              [t.pk for t in collaborators_qs],
        'status':                        cd['status'],
        'sub_status':                    cd.get('sub_status', ''),
        'efforts_issued':                cd.get('efforts_issued', False),
        'efforts_issue_commitment_date': cd.get('efforts_issue_commitment_date'),
        'estimate_link':                 cd.get('estimate_link', ''),
        'estimate_days':                 cd.get('estimate_days'),
        'contingency_pct':               cd.get('contingency_pct'),
        'next_connect_date':             cd.get('next_connect_date'),
        'run_cost_applies':              cd.get('run_cost_applies', False),
        'confidence':                    cd['confidence'],
        'priority':                      cd['priority'],
        'tentative_start_date':          cd.get('tentative_start_date'),
        'tentative_end_date':            cd.get('tentative_end_date'),
        'project_code_note':             cd.get('project_code_note', ''),
    }

def _apply_errors(form, exc: ValidationError):
    if hasattr(exc, 'message_dict'):
        for field, errs in exc.message_dict.items():
            for err in errs:
                form.add_error(field if field != '__all__' else None, err)
    else:
        form.add_error(None, exc.message)

def _list_context_base(all_qs, view_label, view_columns):
    from apps.teams.models import Team
    # Collect all sub-statuses across all statuses for the filter dropdown
    all_sub = ProjectService.get_all_sub_statuses_flat()
    return {
        'total_count':       all_qs.count(),
        'new_count':         all_qs.filter(status=Project.Status.NEW).count(),
        'in_progress_count': all_qs.filter(status=Project.Status.IN_PROGRESS).count(),
        'completed_count':   all_qs.filter(status=Project.Status.COMPLETED).count(),
        'cancelled_count':   all_qs.filter(status=Project.Status.CANCELLED).count(),
        'status_choices':     Project.Status.choices,
        'confidence_choices': Project.Confidence.choices,
        'priority_choices':   Project.Priority.choices,
        'all_sub_statuses':   all_sub,
        'project_types':      ProjectService.get_project_types(),
        'list_views':         ProjectService.get_list_views(),
        'teams':              Team.objects.filter(is_active=True).order_by('name'),
        'view_label':         view_label,
        'active_view':        view_label,
        'view_columns':       view_columns,       # list of column tokens
    }


class ProjectListView(ListView):
    # template_name       = 'projects/project_list.html'
    # context_object_name = 'projects'

    # def get_queryset(self):
    #     return ProjectService.list_projects()

    # def get_context_data(self, **kwargs):
    #     ctx = super().get_context_data(**kwargs)
    #     qs  = self.get_queryset()

    #     ctx['total_count']       = qs.count()
    #     ctx['new_count']         = qs.filter(status=Project.Status.NEW).count()
    #     ctx['in_progress_count'] = qs.filter(status=Project.Status.IN_PROGRESS).count()
    #     ctx['completed_count']   = qs.filter(status=Project.Status.COMPLETED).count()
    #     ctx['cancelled_count']   = qs.filter(status=Project.Status.CANCELLED).count()

    #     ctx['status_choices']     = Project.Status.choices
    #     ctx['confidence_choices'] = Project.Confidence.choices
    #     ctx['priority_choices']   = Project.Priority.choices

    #     from apps.teams.models import Team
    #     ctx['teams'] = Team.objects.filter(is_active=True).order_by('name')

    #     return ctx
    template_name       = 'projects/project_list.html'
    context_object_name = 'projects'
    filter_status       = None
    filter_type         = None
    filter_types        = None   # list — for Maintenance criteria
    view_label          = 'All Projects'
 
    def get_queryset(self):
        qs = ProjectService.list_projects()
        if self.filter_status:
            qs = qs.filter(status=self.filter_status)
        if self.filter_type:
            qs = qs.filter(project_type=self.filter_type)
        if self.filter_types:
            qs = qs.filter(project_type__in=self.filter_types)
        return qs
 
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cols = ProjectService.get_view_columns(self.view_label)
        ctx.update(_list_context_base(ProjectService.list_projects(), self.view_label, cols))
 
        # Build latest-comment lookup dict — one query for all projects in the view
        from .models import ProjectComment
        project_pks = [p.pk for p in ctx['projects']]
        if project_pks and 'latest_comment' in cols:
            # Fetch the most recent comment per project using a single query.
            # We order by -created_at and rely on Python to keep only the first
            # comment seen per project (equivalent to a DISTINCT ON in Postgres).
            comments_qs = (
                ProjectComment.objects
                .filter(project_id__in=project_pks)
                .order_by('project_id', '-created_at')
                .values('project_id', 'body', 'author', 'created_at')
            )
            latest = {}
            for row in comments_qs:
                pid = row['project_id']
                if pid not in latest:          # first row per project = most recent
                    latest[pid] = row
            ctx['latest_comments'] = latest
        else:
            ctx['latest_comments'] = {}
 
        return ctx
    
class NewProjectListView(ProjectListView):
    filter_status = Project.Status.NEW
    view_label    = 'New'
 
 
class InProgressProjectListView(ProjectListView):
    filter_status = Project.Status.IN_PROGRESS
    view_label    = 'In Progress'
 
 
class CompletedProjectListView(ProjectListView):
    filter_status = Project.Status.COMPLETED
    view_label    = 'Completed'
 
 
class CancelledProjectListView(ProjectListView):
    filter_status = Project.Status.CANCELLED
    view_label    = 'Cancelled'
 
 
class BAUProjectListView(ProjectListView):
    filter_type = 'BAU'
    view_label  = 'BAU'
 
 
class MaintenanceProjectListView(ProjectListView):
    # filter_type = 'Maintenance'
    view_label  = 'Maintenance'

    def get_queryset(self):
        criteria = ProjectService.get_maintenance_criteria()
        qs = ProjectService.list_projects()
        if criteria:
            qs = qs.filter(project_type__in=criteria)
        return qs


class ProjectDetailView(DetailView):
    # template_name       = 'projects/project_detail.html'
    # context_object_name = 'project'

    # def get_object(self, queryset=None):
    #     return ProjectService.get_project(self.kwargs['pk'])

    # def get_context_data(self, **kwargs):
    #     ctx     = super().get_context_data(**kwargs)
    #     project = self.get_object()
    #     ctx['comments']      = ProjectService.get_comments(project.pk)
    #     ctx['comment_form']  = ProjectCommentForm()
    #     ctx['sub_statuses']  = ProjectService.get_sub_statuses(project.status)
    #     return ctx

    # def post(self, request, *args, **kwargs):
    #     project = self.get_object()
    #     form    = ProjectCommentForm(request.POST)
    #     if form.is_valid():
    #         ProjectService.add_comment(
    #             project.pk,
    #             form.cleaned_data['body'],
    #             form.cleaned_data.get('author', ''),
    #         )
    #         messages.success(request, 'Comment added.')
    #         return HttpResponseRedirect(
    #             reverse('projects:detail', args=[project.pk]) + '#comments'
    #         )
    #     ctx = self.get_context_data()
    #     ctx['comment_form'] = form
    #     return render(request, self.template_name, ctx)
    template_name = 'projects/project_detail.html'
 
    def _get_project(self, pk):
        return ProjectService.get_project(pk)
 
    def _ctx(self, project):
        return {
            'project':          project,
            'comments':         ProjectService.get_comments(project.pk),
            'comment_form':     ProjectCommentForm(),
            'sub_statuses':     ProjectService.get_sub_statuses(project.status),
            'code_history':     ProjectService.get_code_history(project.pk),
            'estimate_history': ProjectService.get_estimate_history(project.pk),
            'day_price':        ProjectService.get_day_price(),
        }
 
    def get(self, request, pk):
        return render(request, self.template_name, self._ctx(self._get_project(pk)))
 
    def post(self, request, pk):
        project = self._get_project(pk)
        form    = ProjectCommentForm(request.POST)
        if form.is_valid():
            ProjectService.add_comment(
                project.pk,
                form.cleaned_data['body'],
                form.cleaned_data.get('author', ''),
            )
            messages.success(request, 'Comment added.')
            return HttpResponseRedirect(
                reverse('projects:detail', args=[project.pk]) + '#comments'
            )
        ctx = self._ctx(project)
        ctx['comment_form'] = form
        return render(request, self.template_name, ctx)


class ProjectCreateView(View):
    # template_name = 'projects/project_form.html'

    # def _ctx(self, form):
    #     return {
    #         'form':         form,
    #         'is_create':    True,
    #         'all_sub_statuses': ProjectService.all_sub_statuses(),
    #     }

    # def get(self, request):
    #     return render(request, self.template_name, self._ctx(ProjectForm()))

    # def post(self, request):
    #     form = ProjectForm(request.POST)
    #     if not form.is_valid():
    #         return render(request, self.template_name, self._ctx(form))

    #     cd = form.cleaned_data
    #     data = _form_to_service_data(cd)
    #     try:
    #         project = ProjectService.create_project(data)
    #         messages.success(request, f'Project "{project.display_name}" created.')
    #         return HttpResponseRedirect(reverse('projects:detail', args=[project.pk]))
    #     except ValidationError as exc:
    #         _apply_errors(form, exc)
    #         return render(request, self.template_name, self._ctx(form))
    template_name = 'projects/project_form.html'
 
    def _ctx(self, form):
        return {
            'form':             form,
            'is_create':        True,
            'all_sub_statuses': ProjectService.all_sub_statuses(),
            'project_types':    ProjectService.get_project_types(),
            'day_price':        ProjectService.get_day_price(),
        }
 
    def get(self, request):
        return render(request, self.template_name, self._ctx(ProjectForm()))
 
    def post(self, request):
        form = ProjectForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._ctx(form))
        try:
            project = ProjectService.create_project(_form_to_service_data(form.cleaned_data))
            messages.success(request, f'Project "{project.display_name}" created.')
            return HttpResponseRedirect(reverse('projects:detail', args=[project.pk]))
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, self._ctx(form))


class ProjectUpdateView(View):
    # template_name = 'projects/project_form.html'

    # def _get_project(self, pk):
    #     return ProjectService.get_project(pk)

    # def _ctx(self, form, project):
    #     return {
    #         'form':             form,
    #         'project':          project,
    #         'is_create':        False,
    #         'all_sub_statuses': ProjectService.all_sub_statuses(),
    #     }

    # def get(self, request, pk):
    #     project = self._get_project(pk)
    #     form    = ProjectForm(instance=project)
    #     return render(request, self.template_name, self._ctx(form, project))

    # def post(self, request, pk):
    #     project = self._get_project(pk)
    #     form    = ProjectForm(request.POST, instance=project)
    #     if not form.is_valid():
    #         return render(request, self.template_name, self._ctx(form, project))

    #     cd = form.cleaned_data
    #     data = _form_to_service_data(cd)
    #     try:
    #         updated = ProjectService.update_project(pk, data)
    #         messages.success(request, f'Project "{updated.display_name}" updated.')
    #         return HttpResponseRedirect(reverse('projects:detail', args=[pk]))
    #     except ValidationError as exc:
    #         _apply_errors(form, exc)
    #         return render(request, self.template_name, self._ctx(form, project))
    template_name = 'projects/project_form.html'
 
    def _get_project(self, pk):
        return ProjectService.get_project(pk)
 
    def _ctx(self, form, project):
        return {
            'form':             form,
            'project':          project,
            'is_create':        False,
            'all_sub_statuses': ProjectService.all_sub_statuses(),
            'project_types':    ProjectService.get_project_types(),
            'day_price':        ProjectService.get_day_price(),
        }
 
    def get(self, request, pk):
        project = self._get_project(pk)
        form    = ProjectForm(instance=project)
        return render(request, self.template_name, self._ctx(form, project))
 
    def post(self, request, pk):
        project = self._get_project(pk)
        form    = ProjectForm(request.POST, instance=project)
        if not form.is_valid():
            return render(request, self.template_name, self._ctx(form, project))
        try:
            updated = ProjectService.update_project(
                pk, _form_to_service_data(form.cleaned_data)
            )
            messages.success(request, f'Project "{updated.display_name}" updated.')
            return HttpResponseRedirect(reverse('projects:detail', args=[pk]))
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, self._ctx(form, project))
        
class CommentEditView(View):
    def get(self, request, pk, comment_pk):
        comment = get_object_or_404(ProjectComment, pk=comment_pk, project_id=pk)
        return JsonResponse({'ok': True, 'body': comment.body, 'id': comment.pk})
 
    def post(self, request, pk, comment_pk):
        comment = get_object_or_404(ProjectComment, pk=comment_pk, project_id=pk)
        import json
        try:
            payload = json.loads(request.body)
            body    = payload.get('body', '').strip()
        except Exception:
            body = request.POST.get('body', '').strip()
        try:
            updated = ProjectService.edit_comment(comment_pk, body)
            return JsonResponse({
                'ok':        True,
                'body':      updated.body,
                'is_edited': updated.is_edited,
                'updated_at': updated.updated_at.strftime('%d %b %Y, %H:%M'),
            })
        except ValidationError as exc:
            return JsonResponse({'ok': False, 'detail': exc.message}, status=400)
 
 
class CommentDeleteView(View):
    def post(self, request, pk, comment_pk):
        comment = get_object_or_404(ProjectComment, pk=comment_pk, project_id=pk)
        comment_id = comment.pk
        ProjectService.delete_comment(comment_pk)
        return JsonResponse({'ok': True, 'deleted_id': comment_id})
    
class CodeHistoryView(View):
    def get(self, request, pk):
        history = ProjectService.get_code_history(pk)
        data = [{
            'old_code':   h.old_code,
            'new_code':   h.new_code,
            'changed_by': h.changed_by,
            'changed_at': h.changed_at.strftime('%d %b %Y, %H:%M'),
            'note':       h.note,
        } for h in history]
        return JsonResponse({'ok': True, 'history': data})
    
class EstimateHistoryView(View):
    def get(self, request, pk):
        history = ProjectService.get_estimate_history(pk)
        data = [{
            'old_days':        str(h.old_days) if h.old_days is not None else '—',
            'new_days':        str(h.new_days) if h.new_days is not None else '—',
            'old_contingency': str(h.old_contingency) if h.old_contingency is not None else '—',
            'new_contingency': str(h.new_contingency) if h.new_contingency is not None else '—',
            'day_price':       f'£{h.day_price:,.2f}' if h.day_price is not None else '—',
            'total_cost':      f'£{h.total_cost:,.2f}' if h.total_cost is not None else '—',
            'changed_by':      h.changed_by,
            'changed_at':      h.changed_at.strftime('%d %b %Y, %H:%M'),
            'note':            h.note,
        } for h in history]
        return JsonResponse({'ok': True, 'history': data})


class SubStatusApiView(View):
    def get(self, request):
        s = request.GET.get('status', '').upper()
        return JsonResponse({'sub_statuses': ProjectService.get_sub_statuses(s)})

