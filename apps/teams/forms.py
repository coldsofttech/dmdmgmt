from django import forms
from .models import Team


class TeamForm(forms.ModelForm):
    class Meta:
        model  = Team
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. Platform Engineering',
                'autocomplete': 'off',
                'style': 'text-transform:uppercase; font-family: var(--font-mono, monospace);',
                'maxlength': 120,
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'What does this team own or focus on?'
            }),
        }
        error_messages = {
            'name': {
                'required':  'Team name is required.',
                'max_length': 'Team name must be 120 characters or fewer.',
            },
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError('Team name cannot be blank.')

        qs = Team.objects.filter(name=name)
        # qs = Team.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f'A team named "{name}" already exists. '
                'Please choose a different name.'
            )
        return name
    
    def clean_description(self):
        return self.cleaned_data.get('description', '').strip()

    def clean(self):
        cleaned = super().clean()
        return cleaned
