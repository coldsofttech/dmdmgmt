from django.contrib import admin
from .models import (
    ResourcePlan,
    ResourcePlanProject,
    ResourcePlanProjectTeam,
    ResourcePlanPhase,
    ResourcePlanPhaseDependency,
    ResourcePlanAssignment,
    ResourcePlanAssignmentCell,
    ResourcePlanSprintBudget,
    ResourcePlanCapacityOverride,
    ResourcePlanLeafPlaceholder,
    ResourcePlanConflict,
    ResourcePlanAuditLog,
)


class ResourcePlanProjectInline(admin.TabularInline):
    model  = ResourcePlanProject
    extra  = 0
    fields = ['project', 'basis', 'custom_amount', 'days_required',
              'priority_override', 'confidence_override', 'dates_strict']
    readonly_fields = ['days_required']


@admin.register(ResourcePlan)
class ResourcePlanAdmin(admin.ModelAdmin):
    list_display    = ['name', 'financial_year', 'status',
                       'allocation_threshold_pct', 'created_at']
    list_filter     = ['status', 'financial_year']
    search_fields   = ['name']
    readonly_fields = ['created_at', 'updated_at']
    inlines         = [ResourcePlanProjectInline]


@admin.register(ResourcePlanProject)
class ResourcePlanProjectAdmin(admin.ModelAdmin):
    list_display    = ['project', 'plan', 'basis', 'days_required',
                       'effective_priority', 'effective_confidence']
    list_filter     = ['plan', 'basis']
    readonly_fields = ['days_required']
    search_fields   = ['project__project_name', 'project__programme_name']


@admin.register(ResourcePlanProjectTeam)
class ResourcePlanProjectTeamAdmin(admin.ModelAdmin):
    list_display  = ['plan_project', 'team', 'allocation_type',
                     'allocation_value', 'sequence_order']
    list_filter   = ['team', 'allocation_type']


@admin.register(ResourcePlanPhase)
class ResourcePlanPhaseAdmin(admin.ModelAdmin):
    list_display  = ['name', 'plan_project_team', 'sequence_order',
                     'start_sprint', 'end_sprint', 'ramp_pattern']
    list_filter   = ['ramp_pattern', 'dependency_type']
    search_fields = ['name']


@admin.register(ResourcePlanPhaseDependency)
class ResourcePlanPhaseDependencyAdmin(admin.ModelAdmin):
    list_display = ['from_phase', 'dependency_type', 'to_phase']


@admin.register(ResourcePlanAssignment)
class ResourcePlanAssignmentAdmin(admin.ModelAdmin):
    list_display  = ['display_name', 'phase', 'assignment_type',
                     'is_interim', 'pause_from_sprint', 'resume_at_sprint']
    list_filter   = ['assignment_type', 'is_interim']
    search_fields = ['team_member__first_name', 'team_member__last_name',
                     'placeholder_name']


@admin.register(ResourcePlanAssignmentCell)
class ResourcePlanAssignmentCellAdmin(admin.ModelAdmin):
    list_display  = ['assignment', 'sprint', 'days_allocated', 'is_auto', 'is_locked']
    list_filter   = ['is_auto', 'is_locked', 'sprint__financial_year']
    search_fields = ['assignment__team_member__last_name']


@admin.register(ResourcePlanSprintBudget)
class ResourcePlanSprintBudgetAdmin(admin.ModelAdmin):
    list_display = ['plan_project', 'sprint', 'budget_amount']
    list_filter  = ['sprint__financial_year']


@admin.register(ResourcePlanCapacityOverride)
class ResourcePlanCapacityOverrideAdmin(admin.ModelAdmin):
    list_display  = ['team_member', 'sprint', 'reserved_days', 'reason', 'plan']
    list_filter   = ['plan', 'sprint__financial_year']
    search_fields = ['team_member__first_name', 'team_member__last_name', 'reason']


@admin.register(ResourcePlanLeafPlaceholder)
class ResourcePlanLeafPlaceholderAdmin(admin.ModelAdmin):
    list_display  = ['team_member', 'sprint', 'days', 'is_auto_generated', 'plan']
    list_filter   = ['plan', 'is_auto_generated', 'sprint__financial_year']
    search_fields = ['team_member__first_name', 'team_member__last_name']


@admin.register(ResourcePlanConflict)
class ResourcePlanConflictAdmin(admin.ModelAdmin):
    list_display  = ['plan', 'conflict_type', 'severity', 'resolution',
                     'affected_sprint', 'created_at']
    list_filter   = ['conflict_type', 'severity', 'resolution']
    search_fields = ['description']
    readonly_fields = ['created_at']


@admin.register(ResourcePlanAuditLog)
class ResourcePlanAuditLogAdmin(admin.ModelAdmin):
    list_display  = ['plan', 'change_type', 'changed_by', 'changed_at']
    list_filter   = ['change_type', 'plan']
    readonly_fields = ['plan', 'changed_by', 'change_type', 'description', 'changed_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False