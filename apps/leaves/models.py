from django.db import models
from django.core.exceptions import ValidationError
import datetime

def calc_working_days(start_date, end_date, financial_year_id=None):
    if not start_date or not end_date or end_date < start_date:
        return 0
 
    # Build the set of holiday dates for this FY within the range
    holiday_dates = set()
    if financial_year_id:
        try:
            from apps.holidays.models import Holiday
            qs = Holiday.objects.filter(
                financial_year_id=financial_year_id,
                holiday_date__gte=start_date,
                holiday_date__lte=end_date,
            ).values_list('holiday_date', flat=True)
            holiday_dates = set(qs)
        except Exception:
            pass   # holidays app may not exist / table not yet created
 
    total = 0
    current = start_date
    one_day = datetime.timedelta(days=1)
 
    while current <= end_date:
        # weekday(): Mon=0 … Fri=4, Sat=5, Sun=6
        if current.weekday() < 5 and current not in holiday_dates:
            total += 1
        current += one_day
 
    return total


class Leave(models.Model):
    team_member = models.ForeignKey(
        'team_members.TeamMember',
        on_delete=models.CASCADE,
        related_name='leaves',
    )
    financial_year = models.ForeignKey(
        'financial_years.FinancialYear',
        on_delete=models.CASCADE,
        related_name='leaves',
    )
    start_date = models.DateField()
    end_date   = models.DateField()
    days       = models.PositiveSmallIntegerField(
        editable=False,
        help_text=(
            'Auto-calculated working days: calendar days minus weekends '
            'and public holidays from the same financial year.'
        ),
    )
    note = models.TextField(
        blank=True,
        help_text='System-generated note. Not entered by users via the UI.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ['start_date']
 
    def __str__(self):
        return (
            f'{self.team_member} — '
            f'{self.start_date:%d %b %Y} to {self.end_date:%d %b %Y} '
            f'({self.days}d)'
        )
 
    def save(self, *args, **kwargs):
        self.days = calc_working_days(
            self.start_date,
            self.end_date,
            financial_year_id=self.financial_year_id,
        )
        super().save(*args, **kwargs)
 
    def clean(self):
        errors = {}
 
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                errors['end_date'] = 'End date cannot be before start date.'
 
        if self.financial_year_id and self.start_date and self.end_date:
            fy = self.financial_year
            if self.start_date < fy.start_date or self.end_date > fy.end_date:
                errors['start_date'] = (
                    f'Leave dates must fall within {fy.long_fy} '
                    f'({fy.start_date:%d %b %Y} – {fy.end_date:%d %b %Y}).'
                )
 
        if errors:
            raise ValidationError(errors)