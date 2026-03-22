from django import forms
from .models import FinancialYear


class FinancialYearForm(forms.ModelForm):
    class Meta:
        model  = FinancialYear
        fields = ['start_date', 'end_date', 'is_active', 'notes']
        widgets = {
            'start_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control rp-input'},
                format='%Y-%m-%d',
            ),
            'end_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control rp-input'},
                format='%Y-%m-%d',
            ),
            'notes': forms.Textarea(attrs={
                'rows':        3,
                'placeholder': 'Optional notes about this financial year.',
                'class':       'form-control rp-input',
            }),
        }
        error_messages = {
            'start_date': {'required': 'Start date is required.'},
            'end_date':   {'required': 'End date is required.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].input_formats = ['%Y-%m-%d']
        self.fields['end_date'].input_formats   = ['%Y-%m-%d']
        self.fields['is_active'].help_text = (
            'Only one financial year can be active at a time.'
        )

    def clean(self):
        cleaned    = super().clean()
        start_date = cleaned.get('start_date')
        end_date   = cleaned.get('end_date')

        if start_date and end_date:
            if end_date <= start_date:
                self.add_error('end_date', 'End date must be after start date.')
            else:
                delta = (end_date - start_date).days
                if delta < 300 or delta > 400:
                    self.add_error(
                        'end_date',
                        f'A financial year should span approximately 365 days '
                        f'(this spans {delta} days). Please verify the dates.'
                    )

        # Uniqueness check for is_active
        if cleaned.get('is_active'):
            qs = FinancialYear.objects.filter(is_active=True)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    'is_active',
                    'Another financial year is already active. '
                    'Use "Set as Active" on the detail page to switch cleanly.'
                )

        return cleaned