from django.contrib import admin
from .models import Project, ProjectComment


class ProjectCommentInline(admin.TabularInline):
    model          = ProjectComment
    extra          = 0
    readonly_fields = ['body', 'author', 'created_at']
    can_delete     = False
    ordering       = ['-created_at']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display   = [
        'display_name', 'status', 'sub_status', 'assigned_team',
        'confidence', 'priority', 'efforts_issued', 'created_at',
    ]
    list_filter    = ['status', 'confidence', 'priority', 'efforts_issued',
                      'run_cost_applies', 'assigned_team']
    search_fields  = ['project_name', 'programme_name', 'display_name', 'project_code']
    readonly_fields = ['display_name', 'created_at', 'updated_at']
    filter_horizontal = ['collaborators']
    inlines        = [ProjectCommentInline]
    ordering       = ['-created_at']

    fieldsets = (
        ('Identity', {
            'fields': ('programme_name', 'project_name', 'display_name', 'project_code'),
        }),
        ('Contacts', {
            'fields': ('project_contacts', 'finance_contacts'),
        }),
        ('Teams', {
            'fields': ('assigned_team', 'collaborators'),
        }),
        ('Status', {
            'fields': ('status', 'sub_status'),
        }),
        ('Planning', {
            'fields': (
                'efforts_issued', 'efforts_issue_commitment_date',
                'next_connect_date', 'run_cost_applies',
                'confidence', 'priority',
                'tentative_start_date', 'tentative_end_date',
            ),
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(ProjectComment)
class ProjectCommentAdmin(admin.ModelAdmin):
    list_display  = ['project', 'author', 'created_at']
    search_fields = ['body', 'author', 'project__project_name']
    readonly_fields = ['created_at']
    ordering      = ['-created_at']