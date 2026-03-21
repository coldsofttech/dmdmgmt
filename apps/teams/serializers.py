from rest_framework import serializers
from .models import Team

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Team
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate_team(self, value):
        name = value
        if len(name) > 120:
            raise serializers.ValidationError(
                'Team name must be 120 characters or fewer.'
            )
        return name
