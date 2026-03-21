import datetime
from django import forms
from django.utils import timezone
from .models import TeamMember


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model  = TeamMember
        fields = [
            'first_name', 'last_name', 'display_name',
            'role', 'location', 'employee_type',
            'team', 'skills',
            'start_date', 'end_date',
            'default_holidays', 'is_active',
        ]
        widgets = {
            'first_name':   forms.TextInput(attrs={
                'placeholder': 'e.g. Jane',
                'autocomplete': 'off',
                'style': 'text-transform:uppercase; font-family: var(--font-mono, monospace);',
                'maxlength': 80,
            }),
            'last_name':    forms.TextInput(attrs={
                'placeholder': 'e.g. Smith',
                'autocomplete': 'off',
                'style': 'text-transform:uppercase; font-family: var(--font-mono, monospace);',
                'maxlength': 80,
            }),
            'display_name': forms.TextInput(attrs={
                'placeholder': 'Auto-generated. Override if needed.',
                'autocomplete': 'off',
                'style': 'text-transform:uppercase; font-family: var(--font-mono, monospace);',
                'maxlength': 165,
            }),
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date':   forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'default_holidays': forms.NumberInput(attrs={'min': 0, 'max': 365}),
            'skills': forms.SelectMultiple(attrs={
                'class': 'form-select rp-select',
                'size':  '6',
            }),
        }
        error_messages = {
            'first_name': {'required': 'First name is required.'},
            'last_name':  {'required': 'Last name is required.'},
            'start_date': {'required': 'Start date is required.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.teams.models import Team
        from apps.skills.models import Skill

        self.fields['team'].queryset = Team.objects.filter(is_active=True).order_by('name')
        self.fields['team'].required = False
        self.fields['team'].empty_label = '— No team assigned —'

        self.fields['skills'].queryset = Skill.objects.filter(is_active=True).order_by('skill')
        self.fields['skills'].required = False

        if not self.instance.pk:
            try:
                from apps.configurations.services import ConfigurationService
                self.fields['default_holidays'].initial = (
                    ConfigurationService.get_int('DEFAULT_HOLIDAYS', fallback=20)
                )
            except Exception:
                self.fields['default_holidays'].initial = 20

        self.fields['start_date'].input_formats = ['%Y-%m-%d']
        self.fields['end_date'].input_formats   = ['%Y-%m-%d']

    def clean_first_name(self):
        return self.cleaned_data.get('first_name', '').strip()

    def clean_last_name(self):
        return self.cleaned_data.get('last_name', '').strip()

    def clean_display_name(self):
        return self.cleaned_data.get('display_name', '').strip()

    def clean_default_holidays(self):
        val = self.cleaned_data.get('default_holidays', 0)
        if val is None or val < 0:
            raise forms.ValidationError('Holidays cannot be negative.')
        if val > 365:
            raise forms.ValidationError('Holidays cannot exceed 365 days.')
        return val

    def clean(self):
        cleaned    = super().clean()
        start_date = cleaned.get('start_date')
        end_date   = cleaned.get('end_date')

        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'End date cannot be before start date.')

        return cleaned


class MoveTeamForm(forms.Form):
    to_team = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label='— Unassign from current team —',
        label='New team',
        widget=forms.Select(attrs={'class': 'form-select rp-select'}),
    )
    moved_on = forms.DateField(
        label='Effective date',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        input_formats=['%Y-%m-%d'],
    )
    note = forms.CharField(
        required=False,
        label='Reason / note',
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Optional: reason for the move',
            'class': 'form-control rp-input',
        }),
    )

    def __init__(self, *args, member=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.teams.models import Team
        self.fields['to_team'].queryset = Team.objects.filter(is_active=True).order_by('name')
        if not self.data.get('moved_on'):
            self.fields['moved_on'].initial = datetime.date.today().isoformat()

        self._member = member

    def clean_moved_on(self):
        moved_on = self.cleaned_data.get('moved_on')
        if self._member and moved_on:
            if moved_on < self._member.start_date:
                raise forms.ValidationError(
                    'Move date cannot be before the member\'s start date '
                    f'({self._member.start_date}).'
                )
            if self._member.end_date and moved_on > self._member.end_date:
                raise forms.ValidationError(
                    'Move date cannot be after the member\'s end date '
                    f'({self._member.end_date}).'
                )
        return moved_on

    def clean(self):
        cleaned  = super().clean()
        to_team  = cleaned.get('to_team')
        if self._member and to_team and self._member.team == to_team:
            self.add_error(
                'to_team',
                f'This member is already assigned to {to_team.name}.',
            )
        return cleaned