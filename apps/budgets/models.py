from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError


class Budget(models.Model):
    financial_year = models.ForeignKey(
        'financial_years.FinancialYear',
        on_delete=models.CASCADE,
        related_name='budgets',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='budgets',
    )
    budget_allocated = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True,
        help_text='Approved budget ceiling in £. Auto-seeded as £0.00; edit to set real value.',
    )
    refined_budget = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True,
        help_text=(
            'Mid-year re-forecast. When set, remaining_budget is calculated '
            'against this figure instead of budget_allocated.'
        ),
    )
    # Snapshot of project.total_cost — refreshed on every save.
    estimates = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True,
        editable=False,
        help_text='Snapshot of the project total cost at time of last save.',
    )
    # Derived: active_budget - estimates. Null when no active budget is configured.
    remaining_budget = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True,
        editable=False,
        help_text='Auto-calculated remaining budget.',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['project__programme_name', 'project__project_name']
        unique_together = [('project', 'financial_year')]

    def __str__(self):
        return f'{self.project} — {self.financial_year.short_fy}'

    def _refresh_estimates(self):
        if self.project_id:
            try:
                self.estimates = self.project.total_cost
            except Exception:
                self.estimates = None

    def _calc_remaining(self):
        active = self.active_budget
        if active is None:
            self.remaining_budget = None
            return
        estimates = self.estimates or Decimal('0')
        self.remaining_budget = active - estimates

    def save(self, *args, **kwargs):
        self._refresh_estimates()
        self._calc_remaining()
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.budget_allocated is not None and self.budget_allocated < Decimal('0'):
            errors['budget_allocated'] = 'Budget allocated cannot be negative.'
        if self.refined_budget is not None and self.refined_budget < Decimal('0'):
            errors['refined_budget'] = 'Refined budget cannot be negative.'
        if errors:
            raise ValidationError(errors)

    @property
    def active_budget(self):
        return self.refined_budget if self.refined_budget is not None else self.budget_allocated

    @property
    def budget_status(self):
        # Grey states — not yet configured
        if self.budget_allocated is None and self.refined_budget is None:
            return 'unset'
        if (self.budget_allocated == Decimal('0')
                and self.refined_budget is None):
            return 'default'

        active = self.active_budget
        if active is None:
            return 'unset'

        remaining = self.remaining_budget
        if remaining is None:
            return 'unset'

        if remaining > Decimal('0'):
            return 'at_risk'     # budget still available → amber
        if remaining == Decimal('0'):
            return 'on_track'    # exactly consumed → green
        return 'over'            # negative → red

    @property
    def is_over_budget(self):
        return self.budget_status == 'over'

    @property
    def is_on_track(self):
        return self.budget_status == 'on_track'

    @property
    def is_at_risk(self):
        return self.budget_status == 'at_risk'

    @property
    def is_unset(self):
        return self.budget_status in ('unset', 'default')