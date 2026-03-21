from django.db import models
from django.core.exceptions import ValidationError


class TeamMember(models.Model):
    class Role(models.TextChoices):
        ENGINEER      = 'ENGINEER',       'Engineer'
        LEAD_ENGINEER = 'LEAD_ENGINEER',  'Lead Engineer'
        ARCHITECT     = 'ARCHITECT',      'Architect'

    class Location(models.TextChoices):
        ONSITE   = 'ONSITE',   'Onsite'
        OFFSHORE = 'OFFSHORE', 'Offshore'

    class EmployeeType(models.TextChoices):
        EMPLOYEE   = 'EMPLOYEE',   'Employee'
        CONTRACTOR = 'CONTRACTOR', 'Contractor'

    first_name   = models.CharField(max_length=80)
    last_name    = models.CharField(max_length=80)
    display_name = models.CharField(
        max_length=165,
        blank=True,
        help_text='Auto-generated as "Last Name, First Name". Override if needed.',
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ENGINEER,
    )
    location = models.CharField(
        max_length=10,
        choices=Location.choices,
        default=Location.ONSITE,
    )
    employee_type = models.CharField(
        max_length=15,
        choices=EmployeeType.choices,
        default=EmployeeType.CONTRACTOR,
    )
    team = models.ForeignKey(
        'teams.Team',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
    )
    skills = models.ManyToManyField(
        'skills.Skill',
        blank=True,
        related_name='team_members',
    )
    start_date = models.DateField(
        help_text='Date the member joined / became available for planning.',
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date the member leaves. Null means currently active.',
    )

    from apps.configurations.services import ConfigurationService
    holidays = ConfigurationService.get_int('DEFAULT_HOLIDAYS', fallback=20)
    default_holidays = models.PositiveSmallIntegerField(
        default=holidays,
        help_text=(
            'Holiday days per financial year. Defaults to the system '
            'DEFAULT_HOLIDAYS config but can be overridden per member.'
        ),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return self.display_name or f'{self.last_name}, {self.first_name}'

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = f'{self.last_name}, {self.first_name}'
        super().save(*args, **kwargs)

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': 'End date cannot be before start date.'
            })

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'


class TeamMemberHistory(models.Model):
    member = models.ForeignKey(
        TeamMember,
        on_delete=models.CASCADE,
        related_name='team_history',
    )
    from_team = models.ForeignKey(
        'teams.Team',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    to_team = models.ForeignKey(
        'teams.Team',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    moved_on  = models.DateField(help_text='Effective date of the team change.')
    note      = models.TextField(blank=True, help_text='Optional reason for the move.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-moved_on', '-created_at']

    def __str__(self):
        return (
            f'{self.member} — '
            f'{self.from_team or "No team"} → {self.to_team or "No team"} '
            f'on {self.moved_on}'
        )
