from django.contrib import admin
from .models import Budget


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display   = [
        'project', 'financial_year',
        'budget_allocated', 'refined_budget',
        'estimates', 'remaining_budget',
        'is_over_budget', 'created_at',
    ]
    list_filter    = ['financial_year', 'project__assigned_team']
    search_fields  = ['project__project_name', 'project__programme_name',
                      'project__project_code']
    ordering       = ['project__programme_name', 'project__project_name']
    readonly_fields = ['estimates', 'remaining_budget', 'created_at', 'updated_at']

    @admin.display(boolean=True, description='Over budget')
    def is_over_budget(self, obj):
        return obj.is_over_budget