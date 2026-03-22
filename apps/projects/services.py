from decimal import Decimal
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from .models import Project, ProjectComment, EstimateHistory, ProjectCodeHistory


SUB_STATUS_CONFIG_KEYS = {
    Project.Status.NEW:         'PROJECT_SUB_STATUS_NEW',
    Project.Status.IN_PROGRESS: 'PROJECT_SUB_STATUS_IN_PROGRESS',
    Project.Status.COMPLETED:   'PROJECT_SUB_STATUS_COMPLETED',
    Project.Status.CANCELLED:   'PROJECT_SUB_STATUS_CANCELLED',
}

SUB_STATUS_DEFAULTS = {
    Project.Status.NEW:         ['Not Started', 'Under Review',
                                 'Estimates Issued Awaiting Approval',
                                 'Estimates Approved Awaiting Start Date'],
    Project.Status.IN_PROGRESS: ['In Progress'],
    Project.Status.COMPLETED:   ['Completed'],
    Project.Status.CANCELLED:   ['Stopped', 'Cancelled'],
}

ALL_SUPPORTED_COLUMNS = [
    'type', 'team', 'status', 'sub_status', 'priority', 'confidence',
    'efforts', 'commit_date', 'next_connect', 'start', 'end',
    'latest_comment', 'label',
]

VIEW_COLUMN_DEFAULTS = {
    'New':         'type|team|sub_status|priority|efforts|commit_date|next_connect|start|end|latest_comment',
    'In Progress': 'type|team|sub_status|priority|efforts|latest_comment',
    'Completed':   'type|team|priority|efforts|latest_comment',
    'Cancelled':   'type|team|sub_status|priority|efforts|latest_comment',
    'BAU':         'type|team|status|sub_status|priority|efforts|commit_date|start|end|latest_comment',
    'Maintenance': 'type|team|status|sub_status|priority|efforts|commit_date|start|end|latest_comment',
    'All Projects':'type|team|status|sub_status|priority|confidence|efforts|commit_date|next_connect|start|end|latest_comment',
}

VIEW_COLUMN_CONFIG_KEYS = {
    'New':         'PROJECTS_LIST_VIEW_NEW',
    'In Progress': 'PROJECTS_LIST_VIEW_IN_PROGRESS',
    'Completed':   'PROJECTS_LIST_VIEW_COMPLETED',
    'Cancelled':   'PROJECTS_LIST_VIEW_CANCELLED',
    'BAU':         'PROJECTS_LIST_VIEW_BAU',
    'Maintenance': 'PROJECTS_LIST_VIEW_MAINTENANCE',
}


class ProjectService:
    @staticmethod
    def get_project_types() -> list:
        return _cfg_list('PROJECT_TYPES', 'Project|Maintenance|Optimisation|BAU')

    @staticmethod
    def get_list_views() -> list:
        return _cfg_list('PROJECT_LIST_VIEWS', 'All|New|In Progress|Completed|Cancelled|BAU|Maintenance')
    
    @staticmethod
    def get_sub_statuses(status: str):
        key = SUB_STATUS_CONFIG_KEYS.get(status)
        if not key:
            return []
        return _cfg_list(key, '|'.join(SUB_STATUS_DEFAULTS.get(status, [])))

    @staticmethod
    def all_sub_statuses():
        return {s: ProjectService.get_sub_statuses(s) for s in Project.Status.values}
    
    @staticmethod
    def get_all_sub_statuses_flat() -> list:
        seen, result = set(), []
        for s in Project.Status.values:
            for ss in ProjectService.get_sub_statuses(s):
                if ss not in seen:
                    seen.add(ss)
                    result.append(ss)
        return result
    
    @staticmethod
    def get_day_price() -> float:
        try:
            from apps.configurations.services import ConfigurationService
            return ConfigurationService.get_float('STORY_POINT_PRICE', fallback=0.0)
        except Exception:
            return 0.0
        
    @staticmethod
    def get_view_columns(view_label: str) -> list:
        config_key = VIEW_COLUMN_CONFIG_KEYS.get(view_label)
        default    = VIEW_COLUMN_DEFAULTS.get(view_label, VIEW_COLUMN_DEFAULTS['All Projects'])
        if config_key:
            raw = _cfg_str(config_key, default)
        else:
            raw = default
        cols = [c.strip().lower() for c in raw.split('|') if c.strip()]
        # Always include the fixed columns (programme, project, code) — injected by template
        return cols
    
    @staticmethod
    def get_maintenance_criteria() -> list:
        return _cfg_list('PROJECTS_LIST_VIEW_MAINTENANCE_CRITERIA', 'Maintenance')

    @staticmethod
    def list_projects(filters=None):
        qs = (
            Project.objects
            .select_related('assigned_team')
            .prefetch_related('collaborators')
            .all()
        )
        if not filters:
            return qs
        if filters.get('search'):
            from django.db.models import Q
            term = filters['search']
            qs = qs.filter(
                Q(project_name__icontains=term)  |
                Q(programme_name__icontains=term) |
                Q(display_name__icontains=term)   |
                Q(project_code__icontains=term)   |
                Q(label__icontains=term)
            )
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('sub_status'):
            qs = qs.filter(sub_status=filters['sub_status'])
        if filters.get('project_type'):
            qs = qs.filter(project_type=filters['project_type'])
        if filters.get('project_types'):        # list — used for Maintenance criteria
            qs = qs.filter(project_type__in=filters['project_types'])
        if filters.get('assigned_team_id'):
            qs = qs.filter(assigned_team_id=filters['assigned_team_id'])
        if filters.get('confidence'):
            qs = qs.filter(confidence=filters['confidence'])
        if filters.get('priority'):
            qs = qs.filter(priority=filters['priority'])
        return qs

    @staticmethod
    def get_project(project_id: int):
        return (
            Project.objects
            .select_related('assigned_team')
            .prefetch_related('collaborators', 'comments')
            .get(pk=project_id)
        )
    
    @staticmethod
    def get_team_active_projects(team_id: int):
        from django.db.models import Q
        return (
            Project.objects
            .filter(
                Q(assigned_team_id=team_id) | Q(collaborators__id=team_id),
                status__in=[Project.Status.NEW, Project.Status.IN_PROGRESS],
            )
            .select_related('assigned_team')
            .prefetch_related('collaborators')
            .distinct()
            .order_by('status', '-created_at')
        )

    @staticmethod
    @transaction.atomic
    def create_project(data: dict) -> Project:
        collaborator_ids = data.pop('collaborator_ids', [])
        project = Project(
            programme_name                = data.get('programme_name', '').strip(),
            project_name                  = data['project_name'].strip(),
            display_name                  = data.get('display_name', '').strip(),
            project_code                  = data.get('project_code', '').strip(),
            project_type                  = data.get('project_type', 'Project').strip(),
            label                         = data.get('label') or None,
            project_contacts              = data.get('project_contacts', '').strip(),
            finance_contacts              = data.get('finance_contacts', '').strip(),
            assigned_team_id              = data.get('assigned_team_id') or None,
            status                        = data.get('status', Project.Status.NEW),
            sub_status                    = data.get('sub_status', '').strip(),
            efforts_issued                = data.get('efforts_issued', False),
            efforts_issue_commitment_date = data.get('efforts_issue_commitment_date') or None,
            estimate_link                 = data.get('estimate_link', '').strip(),
            estimate_days                 = data.get('estimate_days') or None,
            contingency_pct               = data.get('contingency_pct') or None,
            next_connect_date             = data.get('next_connect_date') or None,
            run_cost_applies              = data.get('run_cost_applies', False),
            confidence                    = data.get('confidence', Project.Confidence.LOW),
            priority                      = data.get('priority', Project.Priority.LOW),
            tentative_start_date          = data.get('tentative_start_date') or None,
            tentative_end_date            = data.get('tentative_end_date') or None,
        )
        project.full_clean()
        project.save()
 
        if collaborator_ids:
            _validate_collaborators(project, collaborator_ids)
            project.collaborators.set(collaborator_ids)
 
        # Seed initial estimate history if estimates provided at creation
        if project.estimate_days is not None:
            _record_estimate_history(project, None, None, None, None)

        try:
            from apps.budgets.services import BudgetService
            active_fy = BudgetService.get_active_fy()
            if active_fy:
                BudgetService.ensure_budget_for_project(project.pk, active_fy.pk)
        except Exception:
            pass
 
        return project

    @staticmethod
    @transaction.atomic
    def update_project(project_id: int, data: dict, changed_by: str = 'System') -> Project:
        project = Project.objects.get(pk=project_id)
        collaborator_ids = data.pop('collaborator_ids', None)
        project_code_note  = data.pop('project_code_note', '')
 
        # ── Track project_code changes ────────────────────
        old_code = project.project_code
        new_code = data.get('project_code', old_code)
        if isinstance(new_code, str):
            new_code = new_code.strip()
        code_changed = new_code != old_code
 
        # ── Track estimate changes ────────────────────────
        old_days        = project.estimate_days
        old_contingency = project.contingency_pct
        new_days        = data.get('estimate_days', old_days)
        new_contingency = data.get('contingency_pct', old_contingency)
        estimates_changed = (
            str(new_days or '') != str(old_days or '') or
            str(new_contingency or '') != str(old_contingency or '')
        )
 
        scalar_fields = [
            'programme_name', 'project_name', 'display_name', 'project_code',
            'project_type', 'label',
            'project_contacts', 'finance_contacts',
            'status', 'sub_status',
            'efforts_issued', 'efforts_issue_commitment_date',
            'estimate_link', 'estimate_days', 'contingency_pct',
            'next_connect_date', 'run_cost_applies',
            'confidence', 'priority',
            'tentative_start_date', 'tentative_end_date',
        ]
        for f in scalar_fields:
            if f in data:
                val = data[f]
                if isinstance(val, str):
                    val = val.strip() or (None if f in ('label',) else val.strip())
                setattr(project, f, val)
 
        if 'assigned_team_id' in data:
            project.assigned_team_id = data['assigned_team_id'] or None
 
        if 'programme_name' in data or 'project_name' in data:
            if not data.get('display_name', '').strip():
                project.display_name = ''
 
        project.full_clean()
        project.save()
 
        if collaborator_ids is not None:
            _validate_collaborators(project, collaborator_ids)
            project.collaborators.set(collaborator_ids)
 
        # ── Write history records ─────────────────────────
        if code_changed:
            ProjectCodeHistory.objects.create(
                project    = project,
                old_code   = old_code,
                new_code   = new_code,
                changed_by = changed_by,
                note       = project_code_note,
            )
 
        if estimates_changed:
            _record_estimate_history(
                project, old_days, new_days, old_contingency, new_contingency, changed_by
            )
 
        return project

    @staticmethod
    def delete_project(project_id: int):
        Project.objects.get(pk=project_id).delete()

    @staticmethod
    def get_code_history(project_id: int):
        return ProjectCodeHistory.objects.filter(project_id=project_id)
    
    @staticmethod
    def get_estimate_history(project_id: int):
        return EstimateHistory.objects.filter(project_id=project_id)

    @staticmethod
    def add_comment(project_id: int, body: str, author: str = ''):
        body = body.strip()
        if not body:
            raise ValidationError('Comment body cannot be blank.')
        project = Project.objects.get(pk=project_id)
        return ProjectComment.objects.create(project=project, body=body, author=author.strip())
    
    @staticmethod
    def edit_comment(comment_id: int, body: str) -> ProjectComment:
        body = body.strip()
        if not body:
            raise ValidationError('Comment body cannot be blank.')
        comment = ProjectComment.objects.get(pk=comment_id)
        comment.body      = body
        comment.is_edited = True
        comment.save(update_fields=['body', 'is_edited', 'updated_at'])
        return comment
 
    @staticmethod
    def delete_comment(comment_id: int) -> None:
        ProjectComment.objects.get(pk=comment_id).delete()

    @staticmethod
    def get_comments(project_id: int):
        return ProjectComment.objects.filter(project_id=project_id)
    
def _cfg_list(code: str, default_pipe: str) -> list:
    try:
        from apps.configurations.services import ConfigurationService
        raw = ConfigurationService.get_str(code, fallback='')
        if raw:
            return [v.strip() for v in raw.split('|') if v.strip()]
    except Exception:
        pass
    return [v.strip() for v in default_pipe.split('|') if v.strip()]
 
 
def _cfg_str(code: str, default: str) -> str:
    try:
        from apps.configurations.services import ConfigurationService
        return ConfigurationService.get_str(code, fallback=default)
    except Exception:
        return default


def _validate_collaborators(project: Project, collaborator_ids: list):
    if project.assigned_team_id and project.assigned_team_id in collaborator_ids:
        raise ValidationError(
            'The assigned team cannot also be listed as a collaborator.'
        )
    
def _record_estimate_history(project, old_days, new_days, old_cont, new_cont,
                              changed_by='System'):
    try:
        from apps.configurations.services import ConfigurationService
        day_price = ConfigurationService.get_float('STORY_POINT_PRICE', fallback=0.0)
    except Exception:
        day_price = 0.0
 
    # Calculate cost for the new values
    if new_days is not None:
        multiplier = 1 + (float(new_cont or 0) / 100)
        total = round(float(new_days) * day_price * multiplier, 2)
    else:
        total = None
 
    EstimateHistory.objects.create(
        project         = project,
        old_days        = old_days,
        new_days        = new_days if new_days is not None else project.estimate_days,
        old_contingency = old_cont,
        new_contingency = new_cont if new_cont is not None else project.contingency_pct,
        day_price       = Decimal(str(day_price)),
        total_cost      = Decimal(str(total)) if total is not None else None,
        changed_by      = changed_by,
    )