from django.db import models
from django.core.exceptions import ValidationError


class Holiday(models.Model):
    financial_year = models.ForeignKey(
        'financial_years.FinancialYear',
        on_delete=models.CASCADE,
        related_name='holidays',
        help_text='Financial year this holiday belongs to.',
    )
    holiday_date = models.DateField(
        help_text='Date of the holiday.',
    )
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text='Short description, e.g. "Christmas Day".',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['holiday_date']
        # One entry per date per FY — prevents accidental duplicates
        unique_together = [('financial_year', 'holiday_date')]

    def __str__(self):
        return f'{self.holiday_date:%d %b %Y} — {self.note or "Holiday"}'

    def clean(self):
        errors = {}

        if self.financial_year_id and self.holiday_date:
            fy = self.financial_year
            if not (fy.start_date <= self.holiday_date <= fy.end_date):
                errors['holiday_date'] = (
                    f'Holiday date must fall within {fy.long_fy} '
                    f'({fy.start_date:%d %b %Y} – {fy.end_date:%d %b %Y}).'
                )

        if errors:
            raise ValidationError(errors)