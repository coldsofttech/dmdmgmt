from django.contrib import admin
from .models import FinancialYear


@admin.register(FinancialYear)
class FinancialYearAdmin(admin.ModelAdmin):
    list_display    = ['long_fy', 'short_fy', 'start_date', 'end_date',
                       'is_active', 'span_days', 'created_at']
    list_filter     = ['is_active']
    readonly_fields = ['long_fy', 'short_fy', 'created_at', 'updated_at']
    ordering        = ['-start_date']

    def span_days(self, obj):
        return obj.span_days
    span_days.short_description = 'Days'