from django.db import models
from django.core.exceptions import ValidationError
import re


class Project(models.Model):
    class Status(models.TextChoices):
        NEW         = 'NEW',         'New'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED   = 'COMPLETED',   'Completed'
        CANCELLED   = 'CANCELLED',   'Cancelled'

    class Confidence(models.TextChoices):
        VERY_HIGH = 'VERY_HIGH', 'Very High'
        HIGH      = 'HIGH',      'High'
        MEDIUM    = 'MEDIUM',    'Medium'
        LOW       = 'LOW',       'Low'

    class Priority(models.TextChoices):
        VERY_HIGH = 'VERY_HIGH', 'Very High'
        HIGH      = 'HIGH',      'High'
        MEDIUM    = 'MEDIUM',    'Medium'
        LOW       = 'LOW',       'Low'

    programme_name = models.CharField(
        max_length=200, blank=True,
        help_text='Optional programme this project belongs to.',
    )
    project_name = models.CharField(max_length=200)
    display_name = models.CharField(
        max_length=405, blank=True,
        help_text='Auto-generated as "Programme Name: Project Name". Override if needed.',
    )
    project_type = models.CharField(
        max_length=80,
        blank=True,
        default='Project',
        help_text=(
            'Configurable via Settings → Configurations (PROJECT_TYPES). '
            'Defaults: Project, Maintenance, Optimisation, BAU.'
        ),
    )
    project_code = models.CharField(
        max_length=100, blank=True,
        help_text='Project code for recharging. Required to move to In Progress.',
    )
    label = models.CharField(
        max_length=30,
        blank=True,
        unique=True,
        null=True,
        help_text=(
            'Unique ALL-CAPS identifier, max 30 chars. '
            'Suggested format: PROGRAMMENAME_PROJECT. '
            'Leave blank to auto-clear (null stored).'
        ),
    )
    project_contacts = models.TextField(
        blank=True,
        help_text='Comma-separated list of project contact names.',
    )
    finance_contacts = models.TextField(
        blank=True,
        help_text='Comma-separated list of finance contact names.',
    )
    assigned_team = models.ForeignKey(
        'teams.Team',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_projects',
        help_text='Primary team responsible for delivery. Required to move to In Progress.',
    )
    collaborators = models.ManyToManyField(
        'teams.Team',
        blank=True,
        related_name='collaborating_projects',
        help_text='Supporting teams. Cannot include the assigned team.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    sub_status = models.CharField(
        max_length=100, blank=True,
        help_text=(
            'Configurable via Settings > Configurations. '
            'Options depend on the current Status.'
        ),
    )
    efforts_issued = models.BooleanField(
        default=False,
        help_text='Have effort estimates been issued?',
    )
    efforts_issue_commitment_date = models.DateField(
        null=True, blank=True,
        help_text='Date by which effort estimates are committed to be issued.',
    )
    estimate_link                 = models.URLField(
        blank=True,
        help_text='Link to the estimate document (e.g. SharePoint).',
    )
    estimate_days = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Effort estimate in person-days.',
    )
    contingency_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Contingency as a percentage of the estimate (e.g. 10 for 10%).',
    )
    total_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Auto-calculated: estimate_days × day_price × (1 + contingency/100). Currency: GBP (£).',
    )
    next_connect_date = models.DateField(
        null=True, blank=True,
        help_text='Date of the next scheduled touchpoint.',
    )
    run_cost_applies = models.BooleanField(
        default=False,
        help_text='Does run cost apply to this project?',
    )
    confidence = models.CharField(
        max_length=10,
        choices=Confidence.choices,
        default=Confidence.LOW,
        help_text='Required to move to In Progress.',
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.LOW,
        help_text='Required to move to In Progress.',
    )
    tentative_start_date = models.DateField(null=True, blank=True)
    tentative_end_date   = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.display_name or self.project_name

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = (
                f'{self.programme_name}: {self.project_name}'
                if self.programme_name
                else self.project_name
            )
        if self.label is not None:
            self.label = self.label.strip().upper() or None
        self._recalculate_cost()
        super().save(*args, **kwargs)

    def _recalculate_cost(self):
        if self.estimate_days is None:
            self.total_cost = None
            return
        try:
            from apps.configurations.services import ConfigurationService
            day_price = ConfigurationService.get_float('STORY_POINT_PRICE', fallback=0.0)
        except Exception:
            day_price = 0.0
        contingency_multiplier = 1 + (float(self.contingency_pct or 0) / 100)
        self.total_cost = round(float(self.estimate_days) * day_price * contingency_multiplier, 2)

    def clean(self):
        errors = {}

        # Validate status transition to IN_PROGRESS
        if self.status == self.Status.IN_PROGRESS:
            missing = []
            if not self.assigned_team_id:
                missing.append('Assigned Team')
            if not self.project_code.strip():
                missing.append('Project Code')
            if not self.confidence:
                missing.append('Confidence')
            if not self.priority:
                missing.append('Priority')
            if missing:
                errors['status'] = (
                    f'To move to In Progress the following fields are required: '
                    f'{", ".join(missing)}.'
                )

        # Validate dates
        if (self.tentative_start_date and self.tentative_end_date
                and self.tentative_end_date < self.tentative_start_date):
            errors['tentative_end_date'] = (
                'Tentative end date cannot be before the start date.'
            )

        if self.label:
            if not re.match(r'^[A-Z0-9_]+$', self.label):
                errors['label'] = 'Label must be ALL CAPS letters, digits and underscores only.'

        if errors:
            raise ValidationError(errors)

    @property
    def project_contacts_list(self):
        return [c.strip() for c in self.project_contacts.split(',') if c.strip()]

    @property
    def finance_contacts_list(self):
        return [c.strip() for c in self.finance_contacts.split(',') if c.strip()]
    
    @property
    def latest_comment(self):
        return self.comments.order_by('-created_at').first()


class ProjectComment(models.Model):
    project    = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    body       = models.TextField()
    author     = models.CharField(
        max_length=120, blank=True, default="System", 
        help_text='Name of the person adding the comment.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited  = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project} — {self.created_at:%d %b %Y}'
    
class ProjectCodeHistory(models.Model):
    project    = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='code_history')
    old_code   = models.CharField(max_length=100, blank=True)
    new_code   = models.CharField(max_length=100, blank=True)
    changed_by = models.CharField(max_length=120, blank=True, default='System')
    changed_at = models.DateTimeField(auto_now_add=True)
    note       = models.TextField(blank=True)
 
    class Meta:
        ordering = ['-changed_at']
 
    def __str__(self):
        return f'{self.project} code: {self.old_code!r} → {self.new_code!r}'
    
class EstimateHistory(models.Model):
    project         = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='estimate_history')
    old_days        = models.DecimalField(max_digits=8,  decimal_places=2, null=True, blank=True)
    new_days        = models.DecimalField(max_digits=8,  decimal_places=2, null=True, blank=True)
    old_contingency = models.DecimalField(max_digits=5,  decimal_places=2, null=True, blank=True)
    new_contingency = models.DecimalField(max_digits=5,  decimal_places=2, null=True, blank=True)
    day_price       = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                          help_text='STORY_POINT_PRICE at time of change.')
    total_cost      = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                          help_text='Calculated total cost at time of change.')
    changed_by      = models.CharField(max_length=120, blank=True, default='System')
    changed_at      = models.DateTimeField(auto_now_add=True)
    note            = models.TextField(blank=True)
 
    class Meta:
        ordering = ['-changed_at']
 
    def __str__(self):
        return f'{self.project} estimate: {self.old_days}d → {self.new_days}d'