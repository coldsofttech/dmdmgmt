from decimal import Decimal
from django import forms
from .models import (
    ResourcePlan,
    ResourcePlanProject,
    ResourcePlanProjectTeam,
    ResourcePlanPhase,
    ResourcePlanAssignment,
    ResourcePlanCapacityOverride,
    ResourcePlanSprintBudget,
)


class ResourcePlanForm(forms.ModelForm):
    class Meta:
        model  = ResourcePlan
        fields = ['name', 'financial_year', 'status',
                  'allocation_threshold_pct', 'scope_notes']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control rp-input',
                'placeholder': 'e.g. FY25-26 Full Delivery Plan',
            }),
            'financial_year': forms.Select(attrs={
                'class': 'form-select rp-select',
            }),
            'status': forms.Select(attrs={'class': 'form-select rp-select'}),
            'allocation_threshold_pct': forms.NumberInput(attrs={
                'class': 'form-control rp-input',
                'step': '0.5', 'min': '0', 'max': '50',
            }),
            'scope_notes': forms.Textarea(attrs={
                'class': 'form-control rp-input',
                'rows': 2,
                'placeholder': 'Optional: describe what this plan covers…',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.financial_years.models import FinancialYear
        self.fields['financial_year'].queryset = (
            FinancialYear.objects.all().order_by('-start_date')
        )
        self.fields['financial_year'].empty_label = '— Select financial year —'
        self.fields['scope_notes'].required = False

        # status is hidden on the create form — set required=False AND a safe initial
        # so that when the field is absent from POST, cleaned_data['status'] = 'DRAFT'
        # rather than '' (which would fail model validation against choices).
        self.fields['status'].required = False
        self.fields['status'].initial  = 'DRAFT'

        # allocation_threshold_pct: ensure a numeric default is always present
        self.fields['allocation_threshold_pct'].required = False
        self.fields['allocation_threshold_pct'].initial  = Decimal('10.00')


class ResourcePlanProjectForm(forms.ModelForm):
    class Meta:
        model  = ResourcePlanProject
        fields = [
            'project', 'basis', 'custom_amount',
            'priority_override', 'confidence_override',
            'dates_strict', 'notes',
        ]
        widgets = {
            'project':             forms.Select(attrs={'class': 'form-select rp-select'}),
            'basis':               forms.Select(attrs={'class': 'form-select rp-select'}),
            'custom_amount':       forms.NumberInput(attrs={
                'class': 'form-control rp-input',
                'step': '0.01', 'min': '0',
                'placeholder': 'Custom £ amount',
            }),
            'priority_override':   forms.Select(attrs={'class': 'form-select rp-select'}),
            'confidence_override': forms.Select(attrs={'class': 'form-select rp-select'}),
            'dates_strict':        forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes':               forms.Textarea(attrs={
                'class': 'form-control rp-input', 'rows': 2,
            }),
        }

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.projects.models import Project
        self.fields['project'].queryset = (
            Project.objects.order_by('programme_name', 'project_name')
        )
        self.fields['project'].empty_label = '— Select project —'
        self.fields['priority_override'].required   = False
        self.fields['confidence_override'].required = False
        self.fields['custom_amount'].required       = False
        self.fields['notes'].required               = False
        # Add blank option to override fields
        for f in ('priority_override', 'confidence_override'):
            self.fields[f].choices = [('', '— Inherit from project —')] + list(
                self.fields[f].choices
            )[1:]  # strip default empty first choice then prepend ours


class ResourcePlanProjectTeamForm(forms.ModelForm):
    class Meta:
        model  = ResourcePlanProjectTeam
        fields = ['team', 'allocation_type', 'allocation_value', 'sequence_order', 'notes']
        widgets = {
            'team':             forms.Select(attrs={'class': 'form-select rp-select'}),
            'allocation_type':  forms.Select(attrs={'class': 'form-select rp-select'}),
            'allocation_value': forms.NumberInput(attrs={
                'class': 'form-control rp-input',
                'step': '0.01', 'min': '0',
            }),
            'sequence_order':   forms.NumberInput(attrs={
                'class': 'form-control rp-input',
                'min': '1',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control rp-input', 'rows': 2,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.teams.models import Team
        self.fields['team'].queryset = Team.objects.filter(is_active=True).order_by('name')
        self.fields['team'].empty_label = '— Select team —'
        self.fields['notes'].required = False


class ResourcePlanPhaseForm(forms.ModelForm):
    class Meta:
        model  = ResourcePlanPhase
        fields = [
            'name', 'sequence_order',
            'start_sprint', 'end_sprint',
            'predecessor_phase', 'dependency_type',
            'ramp_pattern', 'max_days_per_sprint', 'notes',
        ]
        widgets = {
            'name':                forms.TextInput(attrs={'class': 'form-control rp-input'}),
            'sequence_order':      forms.NumberInput(attrs={'class': 'form-control rp-input', 'min': '1'}),
            'start_sprint':        forms.Select(attrs={'class': 'form-select rp-select'}),
            'end_sprint':          forms.Select(attrs={'class': 'form-select rp-select'}),
            'predecessor_phase':   forms.Select(attrs={'class': 'form-select rp-select'}),
            'dependency_type':     forms.Select(attrs={'class': 'form-select rp-select'}),
            'ramp_pattern':        forms.Select(attrs={'class': 'form-select rp-select'}),
            'max_days_per_sprint': forms.NumberInput(attrs={
                'class': 'form-control rp-input',
                'step': '0.25', 'min': '0', 'max': '10',
                'placeholder': 'Default: 10',
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control rp-input', 'rows': 2}),
        }

    def __init__(self, *args, plan=None, plan_project_team=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.sprints.models import Sprint
        if plan:
            fy_id = plan.financial_year_id
            sprint_qs = Sprint.objects.filter(
                financial_year_id=fy_id
            ).order_by('start_date')
        else:
            sprint_qs = Sprint.objects.none()
        self.fields['start_sprint'].queryset   = sprint_qs
        self.fields['end_sprint'].queryset     = sprint_qs
        self.fields['start_sprint'].empty_label  = '— Select sprint —'
        self.fields['end_sprint'].empty_label    = '— Select sprint —'
        self.fields['predecessor_phase'].empty_label = '— None —'
        self.fields['predecessor_phase'].required = False
        self.fields['dependency_type'].required   = False
        self.fields['max_days_per_sprint'].required = False
        self.fields['notes'].required              = False


class ResourcePlanAssignmentForm(forms.ModelForm):
    class Meta:
        model  = ResourcePlanAssignment
        fields = [
            'team_member', 'placeholder_name', 'assignment_type',
            'is_interim', 'replaces_assignment',
            'pause_from_sprint', 'resume_at_sprint',
            'notes',
        ]
        widgets = {
            'team_member':          forms.Select(attrs={'class': 'form-select rp-select'}),
            'placeholder_name':     forms.TextInput(attrs={
                'class': 'form-control rp-input',
                'placeholder': 'e.g. ENGINEER X (TBC)',
            }),
            'assignment_type':      forms.Select(attrs={'class': 'form-select rp-select'}),
            'is_interim':           forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'replaces_assignment':  forms.Select(attrs={'class': 'form-select rp-select'}),
            'pause_from_sprint':    forms.Select(attrs={'class': 'form-select rp-select'}),
            'resume_at_sprint':     forms.Select(attrs={'class': 'form-select rp-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control rp-input', 'rows': 2}),
        }

    def __init__(self, *args, team=None, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.team_members.models import TeamMember
        from apps.sprints.models import Sprint

        if team:
            self.fields['team_member'].queryset = (
                TeamMember.objects.filter(team=team, is_active=True)
                .order_by('last_name', 'first_name')
            )
        else:
            self.fields['team_member'].queryset = TeamMember.objects.none()
        self.fields['team_member'].empty_label = '— Select engineer or leave blank for TBC —'
        self.fields['team_member'].required    = False

        if plan:
            sprint_qs = Sprint.objects.filter(
                financial_year_id=plan.financial_year_id
            ).order_by('start_date')
        else:
            sprint_qs = Sprint.objects.none()
        self.fields['pause_from_sprint'].queryset  = sprint_qs
        self.fields['resume_at_sprint'].queryset   = sprint_qs
        self.fields['pause_from_sprint'].empty_label = '— Not paused —'
        self.fields['resume_at_sprint'].empty_label  = '— N/A —'
        self.fields['pause_from_sprint'].required  = False
        self.fields['resume_at_sprint'].required   = False
        self.fields['placeholder_name'].required   = False
        self.fields['replaces_assignment'].required = False
        self.fields['notes'].required              = False


class ResourcePlanCapacityOverrideForm(forms.ModelForm):
    class Meta:
        model  = ResourcePlanCapacityOverride
        fields = ['team_member', 'sprint', 'reserved_days', 'reason']
        widgets = {
            'team_member':   forms.Select(attrs={'class': 'form-select rp-select'}),
            'sprint':        forms.Select(attrs={'class': 'form-select rp-select'}),
            'reserved_days': forms.NumberInput(attrs={
                'class': 'form-control rp-input',
                'step': '0.25', 'min': '0', 'max': '10',
            }),
            'reason': forms.TextInput(attrs={
                'class': 'form-control rp-input',
                'placeholder': 'e.g. Training week, Adhoc support',
            }),
        }

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.team_members.models import TeamMember
        from apps.sprints.models import Sprint
        self.fields['team_member'].queryset = (
            TeamMember.objects.filter(is_active=True)
            .order_by('team__name', 'last_name', 'first_name')
        )
        self.fields['team_member'].empty_label = '— Select member —'
        if plan:
            self.fields['sprint'].queryset = Sprint.objects.filter(
                financial_year_id=plan.financial_year_id
            ).order_by('start_date')
        else:
            self.fields['sprint'].queryset = Sprint.objects.none()
        self.fields['sprint'].empty_label = '— Select sprint —'
        self.fields['reason'].required = False


class ResourcePlanSprintBudgetForm(forms.ModelForm):
    class Meta:
        model  = ResourcePlanSprintBudget
        fields = ['sprint', 'budget_amount', 'notes']
        widgets = {
            'sprint':        forms.Select(attrs={'class': 'form-select rp-select'}),
            'budget_amount': forms.NumberInput(attrs={
                'class': 'form-control rp-input',
                'step': '0.01', 'min': '0',
                'placeholder': '£0.00',
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control rp-input', 'rows': 2}),
        }

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.sprints.models import Sprint
        if plan:
            self.fields['sprint'].queryset = Sprint.objects.filter(
                financial_year_id=plan.financial_year_id
            ).order_by('start_date')
        else:
            self.fields['sprint'].queryset = Sprint.objects.none()
        self.fields['sprint'].empty_label = '— Select sprint —'
        self.fields['notes'].required = False