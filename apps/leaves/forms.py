from django import forms
from .models import Leave


class LeaveForm(forms.ModelForm):
    class Meta:
        model  = Leave
        fields = ['team_member', 'financial_year', 'start_date', 'end_date']
        widgets = {
            'team_member': forms.Select(attrs={'class': 'form-select rp-select'}),
            'financial_year': forms.Select(attrs={'class': 'form-select rp-select'}),
            'start_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control rp-input'},
                format='%Y-%m-%d',
            ),
            'end_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control rp-input'},
                format='%Y-%m-%d',
            ),
        }

    def __init__(self, *args, team_member=None, financial_year=None, **kwargs):
        super().__init__(*args, **kwargs)

        # ── Team member queryset ──────────────────────────
        from apps.team_members.models import TeamMember
        self.fields['team_member'].queryset = (
            TeamMember.objects.select_related('team')
            .filter(is_active=True)
            .order_by('last_name', 'first_name')
        )
        self.fields['team_member'].empty_label = '— Select team member —'

        # Pre-lock team member when arriving from the member detail page
        if team_member is not None:
            self.fields['team_member'].initial  = team_member
            self.fields['team_member'].required = False          # disabled select sends nothing
            self.fields['team_member'].widget.attrs['disabled'] = True
            self._locked_member = team_member
        else:
            self._locked_member = None

        # ── Financial year queryset ───────────────────────
        from apps.financial_years.models import FinancialYear
        self.fields['financial_year'].queryset = (
            FinancialYear.objects.all().order_by('-start_date')
        )
        self.fields['financial_year'].empty_label = '— Select financial year —'

        # Pre-lock FY when supplied (e.g. from FY detail page)
        if financial_year is not None:
            self.fields['financial_year'].initial  = financial_year
            self.fields['financial_year'].required = False
            self.fields['financial_year'].widget.attrs['disabled'] = True
            self._locked_fy = financial_year
        else:
            self._locked_fy = None

        # ── Fix date parsing under USE_L10N=True ─────────
        # Without localize=False, Django ignores input_formats and uses
        # locale formats (e.g. en-GB: d/m/Y) — rejecting the ISO YYYY-MM-DD
        # that HTML date inputs always send.
        for fname in ('start_date', 'end_date'):
            self.fields[fname].localize      = False
            self.fields[fname].input_formats = ['%Y-%m-%d']

    def clean_team_member(self):
        if self._locked_member is not None:
            return self._locked_member
        return self.cleaned_data.get('team_member')

    def clean_financial_year(self):
        if self._locked_fy is not None:
            return self._locked_fy
        return self.cleaned_data.get('financial_year')

    def clean(self):
        cleaned = super().clean()
        start   = cleaned.get('start_date')
        end     = cleaned.get('end_date')
        fy      = cleaned.get('financial_year')

        if start and end:
            if end < start:
                self.add_error('end_date', 'End date cannot be before start date.')
            elif fy:
                if start < fy.start_date or end > fy.end_date:
                    self.add_error(
                        'start_date',
                        f'Dates must fall within {fy.long_fy} '
                        f'({fy.start_date:%d %b %Y} – {fy.end_date:%d %b %Y}).'
                    )

        return cleaned