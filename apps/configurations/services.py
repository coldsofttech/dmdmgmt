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
