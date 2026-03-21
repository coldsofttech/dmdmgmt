from django.apps import AppConfig


class ConfigurationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name  = 'apps.configurations'
    label = 'configurations'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_seed_defaults, sender=self)


def _seed_defaults(sender, **kwargs):
    try:
        from .models import Configuration
        from .services import CONFIGURATION_DEFAULTS

        for code, meta in CONFIGURATION_DEFAULTS.items():
            Configuration.objects.get_or_create(
                code=code,
                defaults={
                    'label':       meta['label'],
                    'value':       meta['value'],
                    'description': meta['description'],
                },
            )
        # defaults = [
        #     {
        #         'code':        'DEFAULT_HOLIDAYS',
        #         'label':       'Default holidays per financial year',
        #         'value':       '20',
        #         'description': (
        #             'Number of holiday days allocated to each team member '
        #             'per financial year. Used as the baseline when calculating '
        #             'available capacity in sprint planning.'
        #         ),
        #     },
        #     # ── Add future defaults below this line ──────────
        #     # {
        #     #     'code':        'SPRINT_LENGTH_DAYS',
        #     #     'label':       'Default sprint length (days)',
        #     #     'value':       '14',
        #     #     'description': 'Number of calendar days in a standard sprint.',
        #     # },
        # ]
        # for d in defaults:
        #     Configuration.objects.get_or_create(
        #         code=d['code'],
        #         defaults={
        #             'label':       d['label'],
        #             'value':       d['value'],
        #             'description': d['description'],
        #         },
        #     )
    except Exception:
        pass
