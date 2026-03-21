from rest_framework import serializers
from .models import Skill


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model        = Skill
        fields       = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate_skill(self, value):
        code = value.strip().upper()
        if not code.isalnum():
            raise serializers.ValidationError(
                'Skill code must contain only letters and numbers.'
            )
        if len(code) > 20:
            raise serializers.ValidationError(
                'Skill code must be 20 characters or fewer.'
            )
        return code