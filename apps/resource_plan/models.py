"""
Resource Plan — models.py
All 12 models for Phase 1.

Model hierarchy:
  ResourcePlan
    └── ResourcePlanProject           (projects scoped into a plan)
          ├── ResourcePlanSprintBudget  (per-sprint budget release overrides)
          └── ResourcePlanProjectTeam  (teams assigned to a plan-project)
                └── ResourcePlanPhase  (work phases within a project-team)
                      ├── ResourcePlanPhaseDependency  (cross-phase dependencies)
                      └── ResourcePlanAssignment       (engineer on a phase)
                            └── ResourcePlanAssignmentCell  (one cell: assignment × sprint)
  ResourcePlan
    ├── ResourcePlanCapacityOverride   (adhoc capacity reserves per engineer)
    ├── ResourcePlanLeafPlaceholder    (projected leaves not yet in Leaves table)
    ├── ResourcePlanConflict           (conflict log for resolution queue)
    └── ResourcePlanAuditLog           (immutable change log)
"""

from decimal import Decimal, ROUND_HALF_UP
import datetime

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


# ── Utility ───────────────────────────────────────────────

def _round_to_quarter(value):
    """Round a Decimal/float to the nearest 0.25."""
    d = Decimal(str(value))
    return float((d * 4).quantize(Decimal('1'), rounding=ROUND_HALF_UP) / 4)


# ═══════════════════════════════════════════════════════════
#  Tier 1 — Plan scaffold
# ═══════════════════════════════════════════════════════════

class ResourcePlan(models.Model):

    class Status(models.TextChoices):
        DRAFT  = 'DRAFT',  'Draft'
        ACTIVE = 'ACTIVE', 'Active'
        LOCKED = 'LOCKED', 'Locked'

    name            = models.CharField(max_length=200)
    financial_year  = models.ForeignKey(
        'financial_years.FinancialYear',
        on_delete=models.CASCADE,
        related_name='resource_plans',
    )
    status          = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT,
    )
    allocation_threshold_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        help_text=(
            'Acceptable over/under allocation threshold in percent. '
            'Default 10 — e.g. £10k budget, £11k allocated is acceptable (10%), '
            '£13k is flagged.'
        ),
    )
    scope_notes = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-financial_year__start_date', 'name']

    def __str__(self):
        return f'{self.name} ({self.financial_year.short_fy})'


class ResourcePlanProject(models.Model):
    """A project scoped into a plan, with basis and days-required calculation."""

    class Basis(models.TextChoices):
        ESTIMATE = 'ESTIMATE', 'Estimates (total cost)'
        BUDGET   = 'BUDGET',   'Budget (allocated or refined)'
        CUSTOM   = 'CUSTOM',   'Custom amount'

    # Priority / Confidence mirrors Project model choices
    class Priority(models.TextChoices):
        VERY_HIGH = 'VERY_HIGH', 'Very High'
        HIGH      = 'HIGH',      'High'
        MEDIUM    = 'MEDIUM',    'Medium'
        LOW       = 'LOW',       'Low'

    class Confidence(models.TextChoices):
        VERY_HIGH = 'VERY_HIGH', 'Very High'
        HIGH      = 'HIGH',      'High'
        MEDIUM    = 'MEDIUM',    'Medium'
        LOW       = 'LOW',       'Low'

    _PRIORITY_ORDER = {
        'VERY_HIGH': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3,
    }
    _CONFIDENCE_ORDER = {
        'VERY_HIGH': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3,
    }

    plan    = models.ForeignKey(
        ResourcePlan, on_delete=models.CASCADE,
        related_name='plan_projects',
    )
    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE,
        related_name='resource_plan_entries',
    )
    basis         = models.CharField(
        max_length=10, choices=Basis.choices, default=Basis.ESTIMATE,
    )
    custom_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Used only when basis = CUSTOM.',
    )
    # Auto-computed on save — do not set manually
    days_required = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        editable=False,
        help_text='amount ÷ day_rate, rounded to nearest 0.25.',
    )
    priority_override    = models.CharField(
        max_length=10, choices=Priority.choices, blank=True,
        help_text='Overrides project.priority for this plan only.',
    )
    confidence_override  = models.CharField(
        max_length=10, choices=Confidence.choices, blank=True,
        help_text='Overrides project.confidence for this plan only.',
    )
    dates_strict = models.BooleanField(
        default=False,
        help_text=(
            'If True, tentative dates cannot be pushed right even when there is '
            'a capacity conflict. If False, the engine may right-shift.'
        ),
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['plan', 'project__programme_name', 'project__project_name']
        unique_together = [('plan', 'project')]

    def __str__(self):
        return f'{self.plan.name} / {self.project.display_name}'

    # ── Effective priority / confidence ───────────────────

    @property
    def effective_priority(self):
        return self.priority_override or self.project.priority

    @property
    def effective_confidence(self):
        return self.confidence_override or self.project.confidence

    @property
    def priority_rank(self):
        return self._PRIORITY_ORDER.get(self.effective_priority, 99)

    @property
    def confidence_rank(self):
        return self._CONFIDENCE_ORDER.get(self.effective_confidence, 99)

    # ── days_required calculation ─────────────────────────

    def _compute_amount(self):
        """Return the £ amount to use for days calculation based on basis."""
        if self.basis == self.Basis.CUSTOM:
            return self.custom_amount
        if self.basis == self.Basis.ESTIMATE:
            return self.project.total_cost
        if self.basis == self.Basis.BUDGET:
            try:
                budget = self.project.budgets.filter(
                    financial_year=self.plan.financial_year
                ).first()
                return budget.active_budget if budget else None
            except Exception:
                return None
        return None

    def _compute_days_required(self):
        amount = self._compute_amount()
        if amount is None:
            return None
        try:
            from apps.configurations.services import ConfigurationService
            day_rate = ConfigurationService.get_float('STORY_POINT_PRICE', fallback=0.0)
        except Exception:
            day_rate = 0.0
        if day_rate <= 0:
            return None
        import math
        raw = float(amount) / day_rate
        # Ceil to nearest 0.25: always round UP so no effort is under-estimated
        ceiled = math.ceil(raw * 4) / 4
        return Decimal(str(ceiled))

    def save(self, *args, **kwargs):
        self.days_required = self._compute_days_required()
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.basis == self.Basis.CUSTOM and not self.custom_amount:
            errors['custom_amount'] = 'Custom amount is required when basis is "Custom".'
        if errors:
            raise ValidationError(errors)


class ResourcePlanProjectTeam(models.Model):
    """A team assigned to work on one plan-project."""

    class AllocationType(models.TextChoices):
        PERCENT = 'PERCENT', 'Percentage of project (%)'
        DAYS    = 'DAYS',    'Fixed days'
        BUDGET  = 'BUDGET',  'Budget amount (£)'

    plan_project    = models.ForeignKey(
        ResourcePlanProject, on_delete=models.CASCADE,
        related_name='project_teams',
    )
    team            = models.ForeignKey(
        'teams.Team', on_delete=models.CASCADE,
        related_name='resource_plan_teams',
    )
    allocation_type  = models.CharField(
        max_length=10, choices=AllocationType.choices, default=AllocationType.PERCENT,
    )
    allocation_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Percent (0–100), fixed days, or £ amount depending on allocation_type.',
    )
    sequence_order = models.PositiveIntegerField(
        default=1,
        help_text=(
            'Controls the order teams start on this project. '
            'Teams with the same sequence_order run in parallel.'
        ),
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['sequence_order', 'team__name']

    def __str__(self):
        return f'{self.plan_project} → {self.team.name}'

    @property
    def allocated_days(self):
        """Convert allocation to days based on type."""
        pp = self.plan_project
        total_days = pp.days_required
        if total_days is None:
            return None
        v = float(self.allocation_value)
        if self.allocation_type == self.AllocationType.PERCENT:
            return Decimal(str(_round_to_quarter(float(total_days) * v / 100)))
        if self.allocation_type == self.AllocationType.DAYS:
            return Decimal(str(_round_to_quarter(v)))
        if self.allocation_type == self.AllocationType.BUDGET:
            try:
                from apps.configurations.services import ConfigurationService
                rate = ConfigurationService.get_float('STORY_POINT_PRICE', fallback=0.0)
                if rate > 0:
                    return Decimal(str(_round_to_quarter(v / rate)))
            except Exception:
                pass
        return None


# ═══════════════════════════════════════════════════════════
#  Tier 2 — Phase & dependency
# ═══════════════════════════════════════════════════════════

class ResourcePlanPhase(models.Model):
    """A named work phase within one project-team assignment."""

    class DependencyType(models.TextChoices):
        SS = 'SS', 'Start to Start'
        FS = 'FS', 'Finish to Start'
        FF = 'FF', 'Finish to Finish'

    class RampPattern(models.TextChoices):
        FLAT           = 'FLAT',           'Flat (uniform across sprints)'
        RAMP_UP        = 'RAMP_UP',        'Ramp up (gradual increase)'
        RAMP_DOWN      = 'RAMP_DOWN',      'Ramp down (gradual decrease)'
        RAMP_UP_DOWN   = 'RAMP_UP_DOWN',   'Ramp up → Steady → Ramp down'
        RAMP_UP_STEADY = 'RAMP_UP_STEADY', 'Ramp up → Steady'
        STEADY_DOWN    = 'STEADY_DOWN',    'Steady → Ramp down'

    plan_project_team = models.ForeignKey(
        ResourcePlanProjectTeam, on_delete=models.CASCADE,
        related_name='phases',
    )
    name           = models.CharField(max_length=100, default='Phase 1')
    sequence_order = models.PositiveIntegerField(default=1)

    start_sprint = models.ForeignKey(
        'sprints.Sprint', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='phase_starts',
    )
    end_sprint = models.ForeignKey(
        'sprints.Sprint', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='phase_ends',
    )

    predecessor_phase = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='successor_phases',
        help_text='This phase depends on the predecessor phase (cross-project or same).',
    )
    dependency_type = models.CharField(
        max_length=2, choices=DependencyType.choices, blank=True,
        help_text='Only used when predecessor_phase is set.',
    )

    ramp_pattern = models.CharField(
        max_length=20, choices=RampPattern.choices, default=RampPattern.FLAT,
    )
    max_days_per_sprint = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('10'))],
        help_text='Cap on days allocated per sprint for this phase. Null = use global cap (10).',
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['sequence_order']

    def __str__(self):
        return f'{self.plan_project_team} — {self.name}'

    def clean(self):
        errors = {}
        if self.start_sprint and self.end_sprint:
            if self.end_sprint.start_date < self.start_sprint.start_date:
                errors['end_sprint'] = 'End sprint must be on or after start sprint.'
        if self.predecessor_phase and not self.dependency_type:
            errors['dependency_type'] = 'Dependency type is required when a predecessor phase is set.'
        if errors:
            raise ValidationError(errors)

    @property
    def sprint_range(self):
        """Return ordered list of Sprint PKs from start to end (inclusive)."""
        if not self.start_sprint or not self.end_sprint:
            return []
        from apps.sprints.models import Sprint
        return list(
            Sprint.objects.filter(
                financial_year=self.plan_project_team.plan_project.plan.financial_year,
                start_date__gte=self.start_sprint.start_date,
                end_date__lte=self.end_sprint.end_date,
            ).order_by('start_date').values_list('pk', flat=True)
        )


class ResourcePlanPhaseDependency(models.Model):
    """
    Cross-phase dependency (project-to-project level).
    Complements the self-FK on ResourcePlanPhase which handles
    within-project (team-within-project) dependencies.
    """

    class DependencyType(models.TextChoices):
        SS = 'SS', 'Start to Start'
        FS = 'FS', 'Finish to Start'
        FF = 'FF', 'Finish to Finish'

    from_phase      = models.ForeignKey(
        ResourcePlanPhase, on_delete=models.CASCADE,
        related_name='outgoing_dependencies',
    )
    to_phase        = models.ForeignKey(
        ResourcePlanPhase, on_delete=models.CASCADE,
        related_name='incoming_dependencies',
    )
    dependency_type = models.CharField(max_length=2, choices=DependencyType.choices)

    class Meta:
        unique_together = [('from_phase', 'to_phase')]

    def __str__(self):
        return (
            f'{self.from_phase.name} {self.dependency_type} → {self.to_phase.name}'
        )

    def clean(self):
        if self.from_phase_id and self.to_phase_id:
            if self.from_phase_id == self.to_phase_id:
                raise ValidationError('A phase cannot depend on itself.')


# ═══════════════════════════════════════════════════════════
#  Tier 3 — Engineer assignment
# ═══════════════════════════════════════════════════════════

class ResourcePlanAssignment(models.Model):
    """One engineer (or placeholder) assigned to one phase."""

    class AssignmentType(models.TextChoices):
        ENGINEER  = 'ENGINEER',  'Engineer'
        ARCHITECT = 'ARCHITECT', 'Architect'
        ADHOC     = 'ADHOC',     'Adhoc / BAU'
        INTERIM   = 'INTERIM',   'Interim replacement'

    phase = models.ForeignKey(
        ResourcePlanPhase, on_delete=models.CASCADE,
        related_name='assignments',
    )
    # Null team_member = TBC placeholder
    team_member      = models.ForeignKey(
        'team_members.TeamMember', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resource_plan_assignments',
    )
    placeholder_name = models.CharField(
        max_length=100, blank=True,
        help_text='e.g. "ENGINEER X (TBC)" when team_member is not yet known.',
    )
    assignment_type  = models.CharField(
        max_length=10, choices=AssignmentType.choices,
        default=AssignmentType.ENGINEER,
    )

    # Interim replacement fields (3.22)
    is_interim          = models.BooleanField(default=False)
    replaces_assignment = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='interim_replacements',
        help_text='The original assignment this interim covers.',
    )

    # Engineer-level pause (3.14) — more granular than phase-level pause
    pause_from_sprint  = models.ForeignKey(
        'sprints.Sprint', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assignment_pauses',
        help_text='This engineer pauses work from this sprint onwards.',
    )
    resume_at_sprint   = models.ForeignKey(
        'sprints.Sprint', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assignment_resumes',
        help_text='This engineer resumes work at this sprint.',
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['phase', 'team_member__last_name', 'team_member__first_name']

    def __str__(self):
        name = (
            self.team_member.display_name
            if self.team_member
            else self.placeholder_name or 'TBC'
        )
        return f'{self.phase.name} → {name}'

    def clean(self):
        errors = {}
        if not self.team_member and not self.placeholder_name:
            errors['placeholder_name'] = (
                'Either a team member or a placeholder name is required.'
            )
        if self.is_interim and not self.replaces_assignment_id:
            errors['replaces_assignment'] = (
                'An interim assignment must reference the assignment it replaces.'
            )
        if (self.pause_from_sprint and self.resume_at_sprint and
                self.resume_at_sprint.start_date <= self.pause_from_sprint.start_date):
            errors['resume_at_sprint'] = (
                'Resume sprint must be after pause sprint.'
            )
        if errors:
            raise ValidationError(errors)

    @property
    def display_name(self):
        if self.team_member:
            return self.team_member.display_name
        return self.placeholder_name or 'TBC'


class ResourcePlanAssignmentCell(models.Model):
    """
    Atomic grid cell: one assignment × one sprint = one days_allocated value.
    This is the source of truth for the Section 2 grid.
    """

    assignment     = models.ForeignKey(
        ResourcePlanAssignment, on_delete=models.CASCADE,
        related_name='cells',
    )
    sprint         = models.ForeignKey(
        'sprints.Sprint', on_delete=models.CASCADE,
        related_name='assignment_cells',
    )
    days_allocated = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('0'),
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('10')),
        ],
        help_text='Days allocated (0–10). Rounded to nearest 0.25.',
    )
    # Metadata
    is_auto   = models.BooleanField(
        default=True,
        help_text='True = engine-generated. False = manually overridden.',
    )
    is_locked = models.BooleanField(
        default=False,
        help_text='True for past sprints (3.36) — cannot be edited.',
    )

    class Meta:
        ordering = ['sprint__start_date']
        unique_together = [('assignment', 'sprint')]

    def __str__(self):
        return (
            f'{self.assignment.display_name} / {self.sprint.name}: '
            f'{self.days_allocated}d'
        )

    def clean(self):
        errors = {}
        # Enforce 0.25 rounding
        if self.days_allocated is not None:
            rounded = Decimal(str(_round_to_quarter(self.days_allocated)))
            if rounded != self.days_allocated:
                errors['days_allocated'] = (
                    f'Days must be a multiple of 0.25 (got {self.days_allocated}).'
                )
        if self.is_locked:
            errors['days_allocated'] = 'This sprint is locked (past sprint — cannot be edited).'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Auto-round on save
        if self.days_allocated is not None:
            self.days_allocated = Decimal(str(_round_to_quarter(self.days_allocated)))
        # Auto-lock past sprints
        if self.sprint_id and not self.pk:
            from apps.sprints.models import Sprint
            try:
                sprint = Sprint.objects.get(pk=self.sprint_id)
                if sprint.end_date < datetime.date.today():
                    self.is_locked = True
            except Exception:
                pass
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════
#  Tier 4 — Budget & capacity overrides
# ═══════════════════════════════════════════════════════════

class ResourcePlanSprintBudget(models.Model):
    """
    Per-sprint budget release (3.15).
    When set, the engine caps days for this sprint to amount ÷ day_rate
    instead of using the phase-level ramp.
    """
    plan_project  = models.ForeignKey(
        ResourcePlanProject, on_delete=models.CASCADE,
        related_name='sprint_budgets',
    )
    sprint        = models.ForeignKey(
        'sprints.Sprint', on_delete=models.CASCADE,
        related_name='plan_sprint_budgets',
    )
    budget_amount = models.DecimalField(max_digits=14, decimal_places=2)
    notes         = models.TextField(blank=True)

    class Meta:
        ordering = ['sprint__start_date']
        unique_together = [('plan_project', 'sprint')]

    def __str__(self):
        return (
            f'{self.plan_project.project.display_name} '
            f'/ {self.sprint.name}: £{self.budget_amount:,.2f}'
        )


class ResourcePlanCapacityOverride(models.Model):
    """
    Adhoc capacity reserve per engineer per sprint (3.18 / 3.19).
    Deducted from available capacity before allocation begins.
    """
    plan        = models.ForeignKey(
        ResourcePlan, on_delete=models.CASCADE,
        related_name='capacity_overrides',
    )
    team_member = models.ForeignKey(
        'team_members.TeamMember', on_delete=models.CASCADE,
        related_name='capacity_overrides',
    )
    sprint      = models.ForeignKey(
        'sprints.Sprint', on_delete=models.CASCADE,
        related_name='capacity_overrides',
    )
    reserved_days = models.DecimalField(
        max_digits=4, decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('10'))],
    )
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['sprint__start_date', 'team_member__last_name']
        unique_together = [('plan', 'team_member', 'sprint')]

    def __str__(self):
        return (
            f'{self.team_member.display_name} / {self.sprint.name}: '
            f'{self.reserved_days}d reserved'
        )


class ResourcePlanLeafPlaceholder(models.Model):
    """
    Projected leave that does not yet exist in the Leaves table (3.35).
    Auto-generated when a team member's actual leaves are fewer than
    DEFAULT_HOLIDAYS. Stored separately — never touches the Leaves app.
    Days are restricted to 0.5 or 1.0 per sprint.
    """
    DAYS_CHOICES = [
        (Decimal('0.5'), '0.5 day'),
        (Decimal('1.0'), '1 day'),
    ]

    plan        = models.ForeignKey(
        ResourcePlan, on_delete=models.CASCADE,
        related_name='leaf_placeholders',
    )
    team_member = models.ForeignKey(
        'team_members.TeamMember', on_delete=models.CASCADE,
        related_name='leaf_placeholders',
    )
    sprint      = models.ForeignKey(
        'sprints.Sprint', on_delete=models.CASCADE,
        related_name='leaf_placeholders',
    )
    days              = models.DecimalField(
        max_digits=3, decimal_places=1, choices=DAYS_CHOICES, default=Decimal('1.0'),
    )
    is_auto_generated = models.BooleanField(default=True)

    class Meta:
        ordering = ['sprint__start_date', 'team_member__last_name']
        unique_together = [('plan', 'team_member', 'sprint')]

    def __str__(self):
        return (
            f'{self.team_member.display_name} / {self.sprint.name}: '
            f'{self.days}d projected leave'
        )


# ═══════════════════════════════════════════════════════════
#  Tier 5 — Conflict log & audit
# ═══════════════════════════════════════════════════════════

class ResourcePlanConflict(models.Model):

    class ConflictType(models.TextChoices):
        CAPACITY_EXCEEDED    = 'CAPACITY_EXCEEDED',    'Capacity exceeded'
        PRIORITY_CLASH       = 'PRIORITY_CLASH',       'Competing equal priorities'
        OVER_BUDGET          = 'OVER_BUDGET',          'Over budget/estimate'
        UNDER_BUDGET         = 'UNDER_BUDGET',         'Under budget/estimate'
        THRESHOLD_BREACH     = 'THRESHOLD_BREACH',     'Allocation threshold breached'
        ENGINEER_LEAVE       = 'ENGINEER_LEAVE',       'Engineer has leave in sprint'
        ENGINEER_UNAVAILABLE = 'ENGINEER_UNAVAILABLE', 'Engineer unavailable'

    class Severity(models.TextChoices):
        WARNING = 'WARNING', 'Warning'
        ERROR   = 'ERROR',   'Error'

    class Resolution(models.TextChoices):
        PENDING       = 'PENDING',       'Pending user action'
        SPLIT         = 'SPLIT',         'Capacity split between projects'
        PUSHED_RIGHT  = 'PUSHED_RIGHT',  'Lower priority pushed right'
        REPLACED      = 'REPLACED',      'Engineer replaced / interim assigned'
        PLACEHOLDER   = 'PLACEHOLDER',   'Placeholder engineer created'
        DEPRIORITISED = 'DEPRIORITISED', 'Project deprioritised'
        DISMISSED     = 'DISMISSED',     'Dismissed by user'

    plan                = models.ForeignKey(
        ResourcePlan, on_delete=models.CASCADE,
        related_name='conflicts',
    )
    conflict_type       = models.CharField(
        max_length=25, choices=ConflictType.choices,
    )
    severity            = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.WARNING,
    )
    affected_assignment = models.ForeignKey(
        ResourcePlanAssignment, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='conflicts',
    )
    affected_sprint     = models.ForeignKey(
        'sprints.Sprint', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='plan_conflicts',
    )
    description  = models.TextField()
    resolution   = models.CharField(
        max_length=15, choices=Resolution.choices, default=Resolution.PENDING,
    )
    resolved_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'[{self.severity}] {self.get_conflict_type_display()} '
            f'— {self.plan.name} ({self.resolution})'
        )

    @property
    def is_pending(self):
        return self.resolution == self.Resolution.PENDING


class ResourcePlanAuditLog(models.Model):
    """Immutable record of every cell change or plan action."""

    plan        = models.ForeignKey(
        ResourcePlan, on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    changed_by  = models.CharField(max_length=120, default='System')
    change_type = models.CharField(max_length=50)
    description = models.TextField()
    changed_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.plan.name} — {self.change_type} at {self.changed_at:%d %b %Y %H:%M}'