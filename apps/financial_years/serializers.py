from rest_framework import serializers
from .models import FinancialYear


class FinancialYearSerializer(serializers.ModelSerializer):
    span_days     = serializers.IntegerField(source='span_days', read_only=True)
    display_label = serializers.CharField(source='display_label', read_only=True)

    class Meta:
        model  = FinancialYear
        fields = [
            'id',
            'start_date', 'end_date',
            'long_fy', 'short_fy', 'display_label',
            'is_active',
            'notes',
            'span_days',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['long_fy', 'short_fy', 'created_at', 'updated_at']

    def validate(self, attrs):
        start = attrs.get('start_date')
        end   = attrs.get('end_date')
        if start and end:
            if end <= start:
                raise serializers.ValidationError(
                    {'end_date': 'End date must be after start date.'}
                )
            delta = (end - start).days
            if delta < 300 or delta > 400:
                raise serializers.ValidationError(
                    {'end_date': f'Financial year spans {delta} days — expected ~365.'}
                )
        return attrs