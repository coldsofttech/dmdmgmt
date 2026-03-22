from django.contrib import admin
from .models import Leave


@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display   = ['team_member', 'financial_year', 'start_date', 'end_date', 'days', 'created_at']
    list_filter    = ['financial_year', 'team_member__team']
    search_fields  = ['team_member__display_name', 'team_member__first_name', 'team_member__last_name']
    ordering       = ['start_date']
    readonly_fields = ['days', 'created_at', 'updated_at']
    date_hierarchy = 'start_date'