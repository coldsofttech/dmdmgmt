from rest_framework import serializers
from .models import Budget


class BudgetSerializer(serializers.ModelSerializer):
    project_name       = serializers.CharField(source='project.display_name',   read_only=True)
    programme_name     = serializers.CharField(source='project.programme_name',  read_only=True)
    project_code       = serializers.CharField(source='project.project_code',    read_only=True)
    financial_year_short = serializers.CharField(source='financial_year.short_fy', read_only=True)
    financial_year_long  = serializers.CharField(source='financial_year.long_fy',  read_only=True)
    active_budget      = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    is_over_budget     = serializers.BooleanField(read_only=True)
    is_at_risk         = serializers.BooleanField(read_only=True)

    class Meta:
        model  = Budget
        fields = [
            'id',
            'project',           'project_name',   'programme_name', 'project_code',
            'financial_year',    'financial_year_short', 'financial_year_long',
            'budget_allocated',  'refined_budget',
            'estimates',         'remaining_budget',
            'active_budget',     'is_over_budget',  'is_at_risk',
            'notes',
            'created_at',        'updated_at',
        ]
        read_only_fields = ['estimates', 'remaining_budget', 'created_at', 'updated_at']

    def validate(self, attrs):
        for field in ('budget_allocated', 'refined_budget'):
            val = attrs.get(field)
            if val is not None and val < 0:
                raise serializers.ValidationError({field: f'{field} cannot be negative.'})
        return attrs