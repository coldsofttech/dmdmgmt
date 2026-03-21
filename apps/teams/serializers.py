from rest_framework import serializers
from .models import Team

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Team
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
