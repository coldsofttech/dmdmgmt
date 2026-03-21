from django import forms
from .models import Configuration


# class ConfigurationForm(forms.ModelForm):
#     class Meta:
#         model  = Configuration
#         fields = ['code', 'label', 'value', 'description']
#         widgets = {
#             'code': forms.TextInput(attrs={
#                 'placeholder':   'e.g. DEFAULT_HOLIDAYS',
#                 'autocomplete':  'off',
#                 'style':         'text-transform:uppercase; font-family: var(--font-mono, monospace);',
#                 'maxlength':     50,
#             }),
#             'label': forms.TextInput(attrs={
#                 'placeholder': 'e.g. Default holidays per financial year',
#             }),
#             'value': forms.TextInput(attrs={
#                 'placeholder': 'e.g. 20',
#                 'autocomplete': 'off',
#             }),
#             'description': forms.Textarea(attrs={
#                 'rows': 3,
#                 'placeholder': 'What does this configuration control?',
#             }),
#         }
#         error_messages = {
#             'code':  {'required': 'Configuration code is required.'},
#             'label': {'required': 'Label is required.'},
#             'value': {'required': 'Value is required.'},
#         }

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         if self.instance.pk:
#             self.fields['code'].disabled = True
#             self.fields['code'].help_text = 'Code cannot be changed after creation.'

#     def clean_code(self):
#         if self.instance.pk:
#             return self.instance.code

#         code = self.cleaned_data.get('code', '').strip().upper()
#         if not code:
#             raise forms.ValidationError('Code cannot be blank.')

#         import re
#         if not re.match(r'^[A-Z][A-Z0-9_]*$', code):
#             raise forms.ValidationError(
#                 'Code must start with an uppercase letter and contain only '
#                 'uppercase letters, digits, and underscores.'
#             )

#         if Configuration.objects.filter(code=code).exists():
#             raise forms.ValidationError(
#                 f'"{code}" already exists. '
#                 'Please choose a different code.'
#             )
#         return code

#     def clean_label(self):
#         label = self.cleaned_data.get('label', '').strip()
#         if not label:
#             raise forms.ValidationError('Label cannot be blank.')
#         return label

#     def clean_value(self):
#         value = self.cleaned_data.get('value', '').strip()
#         if value == '':
#             raise forms.ValidationError('Value cannot be blank.')
#         return value

#     def clean_description(self):
#         return self.cleaned_data.get('description', '').strip()
    
#     def clean(self):
#         cleaned = super().clean()
#         return cleaned

class ConfigurationValueForm(forms.Form):
    value = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'placeholder':  'e.g. 20',
            'autocomplete': 'off',
            'class':        'form-control rp-input',
        }),
        error_messages={'required': 'Value cannot be blank.'},
    )
 
    def clean_value(self):
        value = self.cleaned_data.get('value', '').strip()
        if not value:
            raise forms.ValidationError('Value cannot be blank.')
        return value
