from django.contrib import admin
from .models import TeamMember, TeamMemberHistory


class TeamMemberHistoryInline(admin.TabularInline):
    model       = TeamMemberHistory
    extra       = 0
    readonly_fields = ['from_team', 'to_team', 'moved_on', 'note', 'created_at']
    can_delete  = False
    ordering    = ['-moved_on']


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display    = [
        'first_name', 'last_name', 'display_name', 'role', 'team', 'location',
        'employee_type', 'is_active', 'start_date', 'end_date',
    ]
    list_filter     = ['is_active', 'role', 'location', 'employee_type', 'team']
    search_fields   = ['first_name', 'last_name', 'display_name']
    readonly_fields = ['display_name', 'created_at', 'updated_at']
    filter_horizontal = ['skills']
    ordering        = ['last_name', 'first_name']
    inlines         = [TeamMemberHistoryInline]

    fieldsets = (
        ('Personal', {
            'fields': ('first_name', 'last_name', 'display_name'),
        }),
        ('Classification', {
            'fields': ('role', 'location', 'employee_type'),
        }),
        ('Assignment', {
            'fields': ('team', 'skills'),
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date'),
        }),
        ('Planning', {
            'fields': ('default_holidays', 'is_active'),
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(TeamMemberHistory)
class TeamMemberHistoryAdmin(admin.ModelAdmin):
    list_display  = ['member', 'from_team', 'to_team', 'moved_on', 'created_at']
    list_filter   = ['to_team', 'from_team']
    search_fields = ['member__first_name', 'member__last_name', 'note']
    readonly_fields = ['created_at']
    ordering      = ['-moved_on']