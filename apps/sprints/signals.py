from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


def _refresh_overlapping_sprints(financial_year_id: int, holiday_date) -> None:
    try:
        from .models import Sprint
        affected = Sprint.objects.filter(
            financial_year_id=financial_year_id,
            start_date__lte=holiday_date,
            end_date__gte=holiday_date,
        )
        for sprint in affected:
            # save() calls _refresh_calculated() which re-queries holidays
            sprint.save(update_fields=[
                'holiday_count', 'working_days', 'updated_at'
            ])
    except Exception:
        # Never let a signal failure surface as an error to the user
        pass


@receiver(post_save, sender='holidays.Holiday')
def on_holiday_saved(sender, instance, **kwargs):
    _refresh_overlapping_sprints(
        financial_year_id=instance.financial_year_id,
        holiday_date=instance.holiday_date,
    )


@receiver(post_delete, sender='holidays.Holiday')
def on_holiday_deleted(sender, instance, **kwargs):
    _refresh_overlapping_sprints(
        financial_year_id=instance.financial_year_id,
        holiday_date=instance.holiday_date,
    )