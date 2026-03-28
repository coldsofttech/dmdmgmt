from rest_framework import serializers
from .models import Sprint


class SprintSerializer(serializers.ModelSerializer):
    financial_year_short = serializers.CharField(source='financial_year.short_fy', read_only=True)
    financial_year_long  = serializers.CharField(source='financial_year.long_fy',  read_only=True)
    status               = serializers.CharField(read_only=True)
    calendar_days        = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Sprint
        fields = [
            'id',
            'financial_year', 'financial_year_short', 'financial_year_long',
            'sprint_number', 'name',
            'start_date', 'end_date',
            'month', 'holiday_count', 'working_days', 'calendar_days',
            'status', 'is_overridden',
            'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'month', 'holiday_count', 'working_days',
            'is_overridden', 'created_at', 'updated_at',
        ]