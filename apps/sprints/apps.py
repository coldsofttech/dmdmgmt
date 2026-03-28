from django.apps import AppConfig


class SprintsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name  = 'apps.sprints'
    label = 'sprints'

    def ready(self):
        # Register the post_save / post_delete signal handlers that keep
        # Sprint.holiday_count and Sprint.working_days in sync whenever a
        # Holiday row is added, changed, or removed.
        import apps.sprints.signals  # noqa: F401