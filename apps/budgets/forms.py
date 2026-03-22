from django import forms
from .models import Budget


class BudgetForm(forms.ModelForm):
    class Meta:
        model  = Budget
        fields = ['project', 'financial_year', 'budget_allocated', 'refined_budget', 'notes']
        widgets = {
            'project':          forms.Select(attrs={'class': 'form-select rp-select'}),
            'financial_year':   forms.Select(attrs={'class': 'form-select rp-select'}),
            'budget_allocated': forms.NumberInput(attrs={
                'class': 'form-control rp-input',
                'placeholder': '0.00',
                'step': '0.01', 'min': '0',
            }),
            'refined_budget': forms.NumberInput(attrs={
                'class': 'form-control rp-input',
                'placeholder': 'Leave blank unless re-forecasting',
                'step': '0.01', 'min': '0',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control rp-input',
                'rows': 3,
                'placeholder': 'Optional notes…',
            }),
        }

    def __init__(self, *args, project=None, financial_year=None, **kwargs):
        super().__init__(*args, **kwargs)

        # ── Project queryset ──────────────────────────────
        from apps.projects.models import Project
        self.fields['project'].queryset = (
            Project.objects.order_by('programme_name', 'project_name')
        )
        self.fields['project'].empty_label = '— Select project —'

        if project is not None:
            self.fields['project'].initial  = project
            self.fields['project'].required = False
            self.fields['project'].widget.attrs['disabled'] = True
            self._locked_project = project
        else:
            self._locked_project = None

        # ── Financial year queryset ───────────────────────
        from apps.financial_years.models import FinancialYear
        self.fields['financial_year'].queryset = (
            FinancialYear.objects.all().order_by('-start_date')
        )
        self.fields['financial_year'].empty_label = '— Select financial year —'

        if financial_year is not None:
            self.fields['financial_year'].initial  = financial_year
            self.fields['financial_year'].required = False
            self.fields['financial_year'].widget.attrs['disabled'] = True
            self._locked_fy = financial_year
        else:
            self._locked_fy = None

        self.fields['budget_allocated'].required = False
        self.fields['refined_budget'].required   = False
        self.fields['notes'].required            = False

    def clean_project(self):
        if self._locked_project is not None:
            return self._locked_project
        return self.cleaned_data.get('project')

    def clean_financial_year(self):
        if self._locked_fy is not None:
            return self._locked_fy
        return self.cleaned_data.get('financial_year')