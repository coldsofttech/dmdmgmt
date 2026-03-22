from django.contrib import admin
from .models import Holiday


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display  = ['holiday_date', 'note', 'financial_year', 'created_at']
    list_filter   = ['financial_year']
    search_fields = ['note']
    ordering      = ['holiday_date']
    date_hierarchy = 'holiday_date'