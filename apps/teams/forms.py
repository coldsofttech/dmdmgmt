from django import forms
from .models import Team


class TeamForm(forms.ModelForm):
    class Meta:
        model  = Team
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. Platform Engineering',
                'autocomplete': 'off',
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

    def clean(self):
        cleaned = super().clean()
        return cleaned
