from django import forms
from .models import Skill


class SkillForm(forms.ModelForm):
    class Meta:
        model  = Skill
        fields = ['skill', 'description', 'is_active']
        widgets = {
            'skill': forms.TextInput(attrs={
                'placeholder': 'e.g. AWSENGINEER',
                'autocomplete': 'off',
                'style': 'text-transform:uppercase; font-family: var(--font-mono, monospace);',
                'maxlength': 20,
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'What does this skill represent?',
            }),
        }
        error_messages = {
            'skill': {
                'required':   'Skill code is required.',
                'max_length': 'Skill code must be 20 characters or fewer.',
            },
        }

    def clean_skill(self):
        code = self.cleaned_data.get('skill', '').strip().upper()
        if not code:
            raise forms.ValidationError('Skill code cannot be blank.')

        if not code.isalnum():
            raise forms.ValidationError(
                'Skill code must contain only letters and numbers (no spaces or symbols).'
            )

        qs = Skill.objects.filter(skill=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f'Skill "{code}" already exists. '
                'Please choose a different code.'
            )
        return code

    def clean_description(self):
        return self.cleaned_data.get('description', '').strip()
    
    def clean(self):
        cleaned = super().clean()
        return cleaned
