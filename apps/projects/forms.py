from django import forms
from .models import Project, ProjectComment
from .services import ProjectService
import re


class ProjectForm(forms.ModelForm):
    project_code_note = forms.CharField(
        required=False,
        label='Reason for code change',
        widget=forms.Textarea(attrs={
            'rows':        2,
            'placeholder': 'Explain why the project code is being changed…',
            'class':       'form-control rp-input',
        }),
    )

    class Meta:
        model  = Project
        fields = [
            'programme_name', 'project_name', 'display_name', 'project_code',
            'project_type', 'label',
            'project_contacts', 'finance_contacts',
            'assigned_team', 'collaborators',
            'status', 'sub_status',
            'efforts_issued', 'efforts_issue_commitment_date',
            'estimate_link', 'estimate_days', 'contingency_pct',
            'next_connect_date', 'run_cost_applies',
            'confidence', 'priority',
            'tentative_start_date', 'tentative_end_date',
        ]
        widgets = {
            'programme_name': forms.TextInput(attrs={
                'placeholder': 'e.g. Digital Transformation', 'autocomplete': 'off',
            }),
            'project_name': forms.TextInput(attrs={
                'placeholder': 'e.g. Customer Portal Rebuild', 'autocomplete': 'off',
            }),
            'display_name': forms.TextInput(attrs={
                'placeholder': 'Auto-generated. Override if needed.',
            }),
            'project_code': forms.TextInput(attrs={
                'placeholder': 'e.g. PRJ-2025-001', 'autocomplete': 'off',
            }),
            'label': forms.TextInput(attrs={
                'placeholder': 'e.g. DIGITALTRANS_PORTAL',
                'autocomplete': 'off',
                'maxlength':   '30',
                'style':       'text-transform:uppercase;font-family:var(--font-mono,monospace);',
                'oninput':     "this.value=this.value.toUpperCase().replace(/[^A-Z0-9_]/g,'')",
            }),
            'project_contacts': forms.TextInput(attrs={
                'placeholder': 'e.g. Jane Smith, John Doe', 'autocomplete': 'off',
            }),
            'finance_contacts': forms.TextInput(attrs={
                'placeholder': 'e.g. Alice Brown', 'autocomplete': 'off',
            }),
            'collaborators': forms.SelectMultiple(attrs={
                'class': 'form-select rp-select', 'size': '5',
            }),
            'estimate_link': forms.URLInput(attrs={
                'placeholder': 'https://confluence.example.com/estimates/…',
                'class': 'form-control rp-input',
            }),
            'estimate_days': forms.NumberInput(attrs={
                'placeholder': 'e.g. 45', 'min': '0', 'step': '0.5',
                'class': 'form-control rp-input',
                'oninput': 'recalcCost()',
            }),
            'contingency_pct': forms.NumberInput(attrs={
                'placeholder': 'e.g. 10', 'min': '0', 'max': '100', 'step': '0.5',
                'class': 'form-control rp-input',
                'oninput': 'recalcCost()',
            }),
            'efforts_issue_commitment_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control rp-input'}, format='%Y-%m-%d',
            ),
            'next_connect_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control rp-input'}, format='%Y-%m-%d',
            ),
            'tentative_start_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control rp-input'}, format='%Y-%m-%d',
            ),
            'tentative_end_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control rp-input'}, format='%Y-%m-%d',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
 
        from apps.teams.models import Team
        active_teams = Team.objects.filter(is_active=True).order_by('name')
 
        self.fields['assigned_team'].queryset   = active_teams
        self.fields['assigned_team'].required   = False
        self.fields['assigned_team'].empty_label = '— No team assigned —'
 
        # ── Collaborators fix (issue 9) ──────────────────────────────────────
        # Must NOT use ModelMultipleChoiceField validation against empty string.
        # We set required=False and provide full queryset so existing selections
        # render correctly and deselection (sending empty POST) clears them.
        self.fields['collaborators'].queryset = active_teams
        self.fields['collaborators'].required = False
 
        # ── Project type ─────────────────────────────────────────────────────
        type_opts = ProjectService.get_project_types()
        self.fields['project_type'] = forms.ChoiceField(
            required=False,
            choices=[('', '— Select type —')] + [(t, t) for t in type_opts],
            initial='Project',
            widget=forms.Select(attrs={'class': 'form-select rp-select'}),
        )
 
        # ── Sub-status ───────────────────────────────────────────────────────
        current_status = (
            self.data.get('status')
            or (self.instance.status if self.instance.pk else Project.Status.NEW)
        )
        self.fields['sub_status'] = forms.ChoiceField(
            required=False,
            choices=self._sub_status_choices(current_status),
            widget=forms.Select(attrs={'class': 'form-select rp-select'}),
        )
 
        # Date input formats
        for f in ['efforts_issue_commitment_date', 'next_connect_date',
                  'tentative_start_date', 'tentative_end_date']:
            self.fields[f].input_formats = ['%Y-%m-%d']
        
        if not self.instance.pk:
            self.fields['project_code_note'].widget = forms.HiddenInput()

    @staticmethod
    def _sub_status_choices(status: str) -> list:
        opts = ProjectService.get_sub_statuses(status)
        return [('', '— Select —')] + [(o, o) for o in opts]

    def clean_project_name(self):
        val = self.cleaned_data.get('project_name', '').strip()
        if not val:
            raise forms.ValidationError('Project name is required.')
        return val

    def clean_display_name(self):
        return self.cleaned_data.get('display_name', '').strip()

    def clean_project_code(self):
        return self.cleaned_data.get('project_code', '').strip()
    
    def clean_label(self):
        raw = self.cleaned_data.get('label')
        if raw is None:
            return None
        val = raw.strip().upper()
        if not val:
            return None    # blank string → null in DB (unique constraint allows this)
 
        if not re.match(r'^[A-Z0-9_]+$', val):
            raise forms.ValidationError(
                'Label must be ALL CAPS letters, digits and underscores only.'
            )
 
        from .models import Project as ProjectModel
        qs = ProjectModel.objects.filter(label=val)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f'Label "{val}" is already in use.')
 
        return val
    
    def clean_project_code_note(self):
        return self.cleaned_data.get('project_code_note', '').strip()
    
    def clean_estimate_days(self):
        val = self.cleaned_data.get('estimate_days')
        if val is not None and val < 0:
            raise forms.ValidationError('Estimate days cannot be negative.')
        return val
    
    def clean_contingency_pct(self):
        val = self.cleaned_data.get('contingency_pct')
        if val is not None and (val < 0 or val > 100):
            raise forms.ValidationError('Contingency must be between 0 and 100.')
        return val

    def clean(self):
        cleaned = super().clean()
 
        if cleaned.get('status') == Project.Status.IN_PROGRESS:
            missing = []
            if not cleaned.get('assigned_team'):          missing.append('Assigned Team')
            if not cleaned.get('project_code', '').strip(): missing.append('Project Code')
            if not cleaned.get('confidence'):             missing.append('Confidence')
            if not cleaned.get('priority'):               missing.append('Priority')
            if missing:
                self.add_error('status',
                    f'To move to In Progress the following fields are required: '
                    f'{", ".join(missing)}.'
                )
 
        assigned      = cleaned.get('assigned_team')
        collaborators = cleaned.get('collaborators') or []
        if assigned and assigned in collaborators:
            self.add_error('collaborators',
                'The assigned team cannot also be listed as a collaborator.')
 
        start = cleaned.get('tentative_start_date')
        end   = cleaned.get('tentative_end_date')
        if start and end and end < start:
            self.add_error('tentative_end_date',
                'Tentative end date cannot be before the start date.')
 
        return cleaned


class ProjectCommentForm(forms.ModelForm):
    class Meta:
        model  = ProjectComment
        fields = ['body', 'author']
        widgets = {
            'body': forms.Textarea(attrs={
                'rows':        3,
                'placeholder': 'Add a discussion point or update…',
                'class':       'form-control rp-input',
            }),
            'author': forms.TextInput(attrs={
                'placeholder': 'Your name (optional)',
                'class':       'form-control rp-input',
            }),
        }

    def clean_body(self):
        body = self.cleaned_data.get('body', '').strip()
        if not body:
            raise forms.ValidationError('Comment cannot be blank.')
        return body
    
class ProjectCommentEditForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control rp-input',
        }),
    )
 
    def clean_body(self):
        body = self.cleaned_data.get('body', '').strip()
        if not body:
            raise forms.ValidationError('Comment cannot be blank.')
        return body