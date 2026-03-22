from django import forms
from .models import Holiday


class HolidayForm(forms.ModelForm):
    class Meta:
        model  = Holiday
        fields = ['financial_year', 'holiday_date', 'note']
        widgets = {
            'financial_year': forms.Select(attrs={
                'class': 'form-select rp-select',
            }),
            'holiday_date': forms.DateInput(
                # format= controls the rendered value (what appears in the field).
                # Parsing is controlled by input_formats + localize on the field itself.
                attrs={'type': 'date', 'class': 'form-control rp-input'},
                format='%Y-%m-%d',
            ),
            'note': forms.TextInput(attrs={
                'placeholder':  'e.g. Christmas Day',
                'class':        'form-control rp-input',
                'autocomplete': 'off',
            }),
        }

    def __init__(self, *args, financial_year=None, **kwargs):
        super().__init__(*args, **kwargs)
 
        from apps.financial_years.models import FinancialYear
        self.fields['financial_year'].queryset    = FinancialYear.objects.all().order_by('-start_date')
        self.fields['financial_year'].empty_label = '— Select financial year —'
 
        if financial_year is not None:
            self.fields['financial_year'].initial  = financial_year
            self.fields['financial_year'].required = False          # ← key fix
            self.fields['financial_year'].widget.attrs['disabled'] = True
            self._locked_fy = financial_year
        else:
            self._locked_fy = None
 
        self.fields['holiday_date'].localize      = False
        self.fields['holiday_date'].input_formats = ['%Y-%m-%d']
 
        self.fields['note'].required = False

    def clean_financial_year(self):
        if self._locked_fy is not None:
            return self._locked_fy
        return self.cleaned_data.get('financial_year')

    def clean(self):
        cleaned = super().clean()
        fy           = cleaned.get('financial_year')
        holiday_date = cleaned.get('holiday_date')

        if fy and holiday_date:
            if not (fy.start_date <= holiday_date <= fy.end_date):
                self.add_error(
                    'holiday_date',
                    f'Date must fall within {fy.long_fy} '
                    f'({fy.start_date:%d %b %Y} – {fy.end_date:%d %b %Y}).'
                )

        return cleaned