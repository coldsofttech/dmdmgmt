import datetime
from django.db import models
from django.core.exceptions import ValidationError


class Sprint(models.Model):
    class Status(models.TextChoices):
        FUTURE    = 'FUTURE',    'Future'
        ACTIVE    = 'ACTIVE',    'Active'
        COMPLETED = 'COMPLETED', 'Completed'

    financial_year = models.ForeignKey(
        'financial_years.FinancialYear',
        on_delete=models.CASCADE,
        related_name='sprints',
        help_text='Financial year this sprint belongs to.',
    )
    sprint_number = models.PositiveIntegerField(
        help_text='Auto-assigned sprint number (e.g. 170). Editable.',
    )
    name = models.CharField(
        max_length=80,
        help_text='Auto-generated as "Sprint <number>". Override as needed.',
    )
    start_date = models.DateField(help_text='First day of the sprint.')
    end_date   = models.DateField(help_text='Last day of the sprint (inclusive).')

    month = models.CharField(
        max_length=20, blank=True, editable=False,
        help_text='Month name derived from end_date (e.g. "April").',
    )
    holiday_count = models.PositiveSmallIntegerField(
        default=0, editable=False,
        help_text='Number of public holidays within this sprint.',
    )
    working_days = models.PositiveSmallIntegerField(
        default=0, editable=False,
        help_text='Working days (Mon–Fri) minus public holidays within this sprint.',
    )

    is_overridden = models.BooleanField(
        default=False,
        help_text='True when the user has manually overridden generated values.',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date']
        unique_together = [('financial_year', 'sprint_number')]

    def __str__(self):
        return f'{self.name} ({self.start_date:%d %b} – {self.end_date:%d %b %Y})'

    def _refresh_calculated(self):
        if self.end_date:
            self.month = self.end_date.strftime('%B')   # e.g. "April"

        if self.start_date and self.end_date:
            fy_id = self.financial_year_id
            # Count public holidays in range
            try:
                from apps.holidays.models import Holiday
                self.holiday_count = Holiday.objects.filter(
                    financial_year_id=fy_id,
                    holiday_date__gte=self.start_date,
                    holiday_date__lte=self.end_date,
                ).count()
            except Exception:
                self.holiday_count = 0

            # Working days = Mon–Fri days minus public holidays
            hol_dates = set()
            try:
                from apps.holidays.models import Holiday
                hol_dates = set(
                    Holiday.objects.filter(
                        financial_year_id=fy_id,
                        holiday_date__gte=self.start_date,
                        holiday_date__lte=self.end_date,
                    ).values_list('holiday_date', flat=True)
                )
            except Exception:
                pass

            total = 0
            cur   = self.start_date
            one   = datetime.timedelta(days=1)
            while cur <= self.end_date:
                if cur.weekday() < 5 and cur not in hol_dates:
                    total += 1
                cur += one
            self.working_days = total

    def save(self, *args, **kwargs):
        self._refresh_calculated()
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                errors['end_date'] = 'End date cannot be before start date.'
        if self.financial_year_id and self.start_date and self.end_date:
            fy = self.financial_year
            if self.start_date < fy.start_date:
                errors['start_date'] = f'Start date is before the FY start ({fy.start_date:%d %b %Y}).'
            if self.end_date > fy.end_date:
                errors['end_date'] = f'End date is after the FY end ({fy.end_date:%d %b %Y}).'
        if errors:
            raise ValidationError(errors)

    @property
    def status(self):
        today = datetime.date.today()
        if self.start_date > today:
            return self.Status.FUTURE
        if self.end_date < today:
            return self.Status.COMPLETED
        return self.Status.ACTIVE

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def calendar_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0