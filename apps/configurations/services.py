from django.core.exceptions import ValidationError, ObjectDoesNotExist
from .models import Configuration

CONFIGURATION_DEFAULTS = {
    'DEFAULT_HOLIDAYS': {
        'label':       'Default holidays per financial year',
        'value':       '20',
        'description': (
            'Number of holiday days allocated to each team member '
            'per financial year. Used as the baseline when calculating '
            'available capacity in sprint planning.'
        ),
    },
    'PROJECT_SUB_STATUS_NEW': {
        'label':       'Project sub-statuses for New',
        'value':       'Not Started|Under Review|Estimates Issued Awaiting Approval|Estimates Approved Awaiting Start Date',
        'description': (
            'Pipe-separated sub-status options shown when a project '
            'status is New. Edit the value to customise the list.'
        ),
    },
    'PROJECT_SUB_STATUS_IN_PROGRESS': {
        'label':       'Project sub-statuses for In Progress',
        'value':       'In Progress',
        'description': 'Pipe-separated sub-status options for In Progress projects.',
    },
    'PROJECT_SUB_STATUS_COMPLETED': {
        'label':       'Project sub-statuses for Completed',
        'value':       'Completed',
        'description': 'Pipe-separated sub-status options for Completed projects.',
    },
    'PROJECT_SUB_STATUS_CANCELLED': {
        'label':       'Project sub-statuses for Cancelled',
        'value':       'Stopped|Cancelled',
        'description': 'Pipe-separated sub-status options for Cancelled projects.',
    },
    'PROJECT_TYPES': {
        'label':       'Project types',
        'value':       'Project|Maintenance|Optimisation|BAU',
        'description': (
            'Pipe-separated list of project type options shown in the '
            'project form. Edit to add or rename types.'
        ),
    },
    'PROJECT_LIST_VIEWS': {
        'label': 'Project list views (dropdown)',
        'value': 'All|New|In Progress|Completed|Cancelled|BAU|Maintenance',
        'description': 'Pipe-separated list of views shown in the Projects dropdown.',
    },
    'PROJECTS_LIST_VIEW_NEW': {
        'label': 'Columns for New projects view',
        'value': 'type|team|sub_status|priority|efforts|commit_date|next_connect|start|end|latest_comment',
        'description': (
            'Pipe-separated column names for the New projects list view. '
            'Programme, Project and Code are always shown. '
            'Supported: type, team, status, sub_status, priority, confidence, '
            'efforts, commit_date, next_connect, start, end, latest_comment, label.'
        ),
    },
    'PROJECTS_LIST_VIEW_IN_PROGRESS': {
        'label': 'Columns for In Progress projects view',
        'value': 'type|team|sub_status|priority|efforts|latest_comment',
        'description': (
            'Pipe-separated column names for the In Progress list view. '
            'Supported: type, team, status, sub_status, priority, confidence, '
            'efforts, commit_date, next_connect, start, end, latest_comment, label.'
        ),
    },
    'PROJECTS_LIST_VIEW_COMPLETED': {
        'label': 'Columns for Completed projects view',
        'value': 'type|team|priority|efforts|latest_comment',
        'description': (
            'Pipe-separated column names for the Completed list view. '
            'Supported: type, team, status, sub_status, priority, confidence, '
            'efforts, commit_date, next_connect, start, end, latest_comment, label.'
        ),
    },
    'PROJECTS_LIST_VIEW_CANCELLED': {
        'label': 'Columns for Cancelled projects view',
        'value': 'type|team|sub_status|priority|efforts|latest_comment',
        'description': (
            'Pipe-separated column names for the Cancelled list view. '
            'Supported: type, team, status, sub_status, priority, confidence, '
            'efforts, commit_date, next_connect, start, end, latest_comment, label.'
        ),
    },
    'PROJECTS_LIST_VIEW_BAU': {
        'label': 'Columns for BAU projects view',
        'value': 'type|team|status|sub_status|priority|efforts|commit_date|start|end|latest_comment',
        'description': (
            'Pipe-separated column names for the BAU list view. '
            'Supported: type, team, status, sub_status, priority, confidence, '
            'efforts, commit_date, next_connect, start, end, latest_comment, label.'
        ),
    },
    'PROJECTS_LIST_VIEW_MAINTENANCE': {
        'label': 'Columns for Maintenance projects view',
        'value': 'type|team|status|sub_status|priority|efforts|commit_date|start|end|latest_comment',
        'description': (
            'Pipe-separated column names for the Maintenance list view. '
            'Supported: type, team, status, sub_status, priority, confidence, '
            'efforts, commit_date, next_connect, start, end, latest_comment, label.'
        ),
    },
    'PROJECTS_LIST_VIEW_MAINTENANCE_CRITERIA': {
        'label': 'Project types included in Maintenance view',
        'value': 'Maintenance',
        'description': (
            'Pipe-separated project types to include in the Maintenance view. '
            'Default: Maintenance. Add others (e.g. Optimisation) to widen the filter.'
        ),
    },
    'STORY_POINT_PRICE': {
        'label': 'Standard day price (£)',
        'value': '0.00',
        'description': (
            'Standard price per person-day in GBP (£). '
            'Used to calculate project total cost: '
            'estimate_days × day_price × (1 + contingency%).'
        ),
    }
    # ── Add future built-in configs below ─────────────────
    # 'SPRINT_LENGTH_DAYS': {
    #     'label':       'Default sprint length (days)',
    #     'value':       '14',
    #     'description': 'Number of calendar days in a standard sprint.',
    # },
}


class ConfigurationService:
    @staticmethod
    def list_configs(filters=None):
        qs = Configuration.objects.all()
        if not filters:
            return qs
        if filters.get('search'):
            term = filters['search']
            qs = qs.filter(code__icontains=term) | qs.filter(label__icontains=term)
        return qs

    @staticmethod
    def get_config(config_id: int):
        return Configuration.objects.get(pk=config_id)

    @staticmethod
    def get_by_code(code: str):
        return Configuration.objects.get(code=code.strip().upper())

    # @staticmethod
    # def create_config(data: dict) -> Configuration:
    #     code = data.get('code', '').strip().upper()
    #     if Configuration.objects.filter(code=code).exists():
    #         raise ValidationError(f"Configuration '{code}' already exists.")
    #     config = Configuration(
    #         code        = code,
    #         label       = data.get('label', '').strip(),
    #         value       = data.get('value', '').strip(),
    #         description = data.get('description', '').strip(),
    #     )
    #     config.full_clean()
    #     config.save()
    #     return config

    # @staticmethod
    # def update_config(config_id: int, data: dict) -> Configuration:
    #     config = Configuration.objects.get(pk=config_id)
    #     if 'value' in data:
    #         config.value = str(data['value']).strip()

    #     config.full_clean()
    #     config.save()
    #     return config

    @staticmethod
    def update_config(config_id: int, value: str) -> Configuration:
        value = str(value).strip()
        if not value:
            raise ValidationError('Value cannot be blank.')
 
        config = Configuration.objects.get(pk=config_id)
        config.value = value
        config.full_clean()
        config.save(update_fields=['value', 'updated_at'])
        return config

    # @staticmethod
    # def delete_config(config_id: int) -> None:
    #     Configuration.objects.get(pk=config_id).delete()

    @staticmethod
    def get_default_value(code: str) -> str:
        entry = CONFIGURATION_DEFAULTS.get(code.strip().upper())
        return entry['value'] if entry else None
    
    @staticmethod
    def reset_to_default(config_id: int) -> Configuration:
        config = Configuration.objects.get(pk=config_id)
        default = CONFIGURATION_DEFAULTS.get(config.code)
        if default is None:
            raise ValidationError(
                f'No factory default is registered for "{config.code}".'
            )
        config.value = default['value']
        config.full_clean()
        config.save(update_fields=['value', 'updated_at'])
        return config

    @staticmethod
    def get_int(code: str, fallback: int = 0) -> int:
        try:
            cfg = Configuration.objects.get(code=code.strip().upper())
            return int(cfg.value)
        except (ObjectDoesNotExist, ValueError, TypeError):
            return fallback

    @staticmethod
    def get_str(code: str, fallback: str = '') -> str:
        try:
            return Configuration.objects.get(code=code.strip().upper()).value
        except ObjectDoesNotExist:
            return fallback

    @staticmethod
    def get_float(code: str, fallback: float = 0.0) -> float:
        try:
            cfg = Configuration.objects.get(code=code.strip().upper())
            return float(cfg.value)
        except (ObjectDoesNotExist, ValueError, TypeError):
            return fallback

    @staticmethod
    def get_bool(code: str, fallback: bool = False) -> bool:
        try:
            cfg = Configuration.objects.get(code=code.strip().upper())
            return cfg.value.strip().lower() in ('1', 'true', 'yes', 'on')
        except ObjectDoesNotExist:
            return fallback
