from django.contrib import admin
from .models import Sprint


@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):
    list_display    = ['name', 'financial_year', 'start_date', 'end_date',
                       'month', 'working_days', 'holiday_count', 'is_overridden']
    list_filter     = ['financial_year', 'month', 'is_overridden']
    search_fields   = ['name']
    ordering        = ['financial_year', 'start_date']
    readonly_fields = ['month', 'working_days', 'holiday_count', 'created_at', 'updated_at']
    date_hierarchy  = 'start_date'