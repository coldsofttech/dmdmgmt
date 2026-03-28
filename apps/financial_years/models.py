from django.db import models
from django.core.exceptions import ValidationError


class FinancialYear(models.Model):
    start_date = models.DateField(unique=True)
    end_date   = models.DateField(unique=True)
    # end_date = models.DateField(
    #     null=True, blank=True, unique=True,
    #     help_text=(
    #         'Set automatically from the last sprint end date when sprints are '
    #         'generated. Leave blank on creation.'
    #     ),
    # )

    # Auto-calculated on save — never set manually
    long_fy  = models.CharField(max_length=20, blank=True, editable=False)
    short_fy = models.CharField(max_length=12, blank=True, editable=False)

    is_active = models.BooleanField(
        default=False,
        help_text='Mark as the currently active financial year.',
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.long_fy or f'{self.start_date} → {self.end_date}'
        # if self.long_fy:
        #     return self.long_fy
        # if self.start_date:
        #     return f'FY starting {self.start_date:%d %b %Y}'
        # return '(New financial year)'

    def _calculate_labels(self):
        if not (self.start_date and self.end_date):
            return
        start_yr = self.start_date.year
        end_yr   = self.end_date.year
        self.long_fy  = f'FY{start_yr}-{end_yr}'
        self.short_fy = f'FY{str(start_yr)[2:]}-{str(end_yr)[2:]}'
        # if not self.start_date:
        #     return
        # start_yr = self.start_date.year
        # if self.end_date:
        #     end_yr = self.end_date.year
        # else:
        #     # Provisional: assume FY spans two calendar years
        #     end_yr = start_yr + 1
        # self.long_fy  = f'FY{start_yr}-{end_yr}'
        # self.short_fy = f'FY{str(start_yr)[2:]}-{str(end_yr)[2:]}'

    def save(self, *args, **kwargs):
        self._calculate_labels()
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}

        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                errors['end_date'] = 'End date must be after start date.'

            # Warn if span is very far from 365 days (likely a data-entry mistake)
            delta = (self.end_date - self.start_date).days
            if delta < 300 or delta > 400:
                errors['end_date'] = (
                    f'A financial year should span approximately 365 days '
                    f'(this spans {delta} days). Please verify the dates.'
                )

        # Only one FY should be active at a time
        if self.is_active:
            qs = FinancialYear.objects.filter(is_active=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                errors['is_active'] = (
                    'Another financial year is already marked as active. '
                    'Deactivate it first, or save this one as inactive and '
                    'switch via the detail page.'
                )

        if errors:
            raise ValidationError(errors)
        # errors = {}
 
        # if self.start_date and self.end_date:
        #     if self.end_date <= self.start_date:
        #         errors['end_date'] = 'End date must be after start date.'
 
        # # Only one FY should be active at a time
        # if self.is_active:
        #     qs = FinancialYear.objects.filter(is_active=True)
        #     if self.pk:
        #         qs = qs.exclude(pk=self.pk)
        #     if qs.exists():
        #         errors['is_active'] = (
        #             'Another financial year is already marked as active. '
        #             'Deactivate it first, or use the Set as Active button on '
        #             'the detail page to switch cleanly.'
        #         )
 
        # if errors:
        #     raise ValidationError(errors)

    @property
    def display_label(self):
        return self.short_fy or str(self)

    @property
    def span_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return None
    
    # @property
    # def has_end_date(self):
    #     return self.end_date is not None
    
    # @property
    # def days_remaining(self):
    #     if not self.end_date:
    #         return None
    #     import datetime
    #     remaining = (self.end_date - datetime.date.today()).days
    #     return max(remaining, 0)