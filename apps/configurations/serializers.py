from rest_framework import serializers
from .models import Configuration
import re


class ConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model        = Configuration
        fields       = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate_code(self, value):
        code = value.strip().upper()
        if not re.match(r'^[A-Z][A-Z0-9_]*$', code):
            raise serializers.ValidationError(
                'Code must start with an uppercase letter and contain only '
                'uppercase letters, digits, and underscores.'
            )
        if len(code) > 50:
            raise serializers.ValidationError('Code must be 50 characters or fewer.')
        return code

    def validate_value(self, value):
        if str(value).strip() == '':
            raise serializers.ValidationError('Value cannot be blank.')
        return str(value).strip()

    def update(self, instance, validated_data):
        validated_data.pop('code', None)
        return super().update(instance, validated_data)
