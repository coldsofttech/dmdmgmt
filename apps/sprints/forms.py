from django import forms
from .models import Sprint


class SprintGenerateForm(forms.Form):
    financial_year = forms.ModelChoiceField(
        queryset=None,
        empty_label='— Select financial year —',
        widget=forms.Select(attrs={'class': 'form-select rp-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.financial_years.models import FinancialYear
        self.fields['financial_year'].queryset = (
            FinancialYear.objects.all().order_by('-start_date')
        )


class SprintForm(forms.ModelForm):
    class Meta:
        model  = Sprint
        fields = ['financial_year', 'sprint_number', 'name',
                  'start_date', 'end_date', 'notes']
        widgets = {
            'financial_year': forms.Select(attrs={'class': 'form-select rp-select'}),
            'sprint_number':  forms.NumberInput(
                attrs={'class': 'form-control rp-input', 'min': '1'}
            ),
            'name': forms.TextInput(attrs={'class': 'form-control rp-input'}),
            'start_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control rp-input'},
                format='%Y-%m-%d',
            ),
            'end_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control rp-input'},
                format='%Y-%m-%d',
            ),
            'notes': forms.Textarea(
                attrs={'class': 'form-control rp-input', 'rows': 2}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.financial_years.models import FinancialYear
        self.fields['financial_year'].queryset = (
            FinancialYear.objects.all().order_by('-start_date')
        )
        self.fields['financial_year'].empty_label = '— Select financial year —'
        self.fields['notes'].required = False
        for fname in ('start_date', 'end_date'):
            self.fields[fname].localize      = False
            self.fields[fname].input_formats = ['%Y-%m-%d']