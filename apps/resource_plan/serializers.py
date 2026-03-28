from rest_framework import serializers
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
)


class ResourcePlanSerializer(serializers.ModelSerializer):
    financial_year_short = serializers.CharField(
        source='financial_year.short_fy', read_only=True
    )
    financial_year_long = serializers.CharField(
        source='financial_year.long_fy', read_only=True
    )
    pending_conflict_count = serializers.SerializerMethodField()

    class Meta:
        model  = ResourcePlan
        fields = [
            'id', 'name', 'financial_year', 'financial_year_short',
            'financial_year_long', 'status', 'allocation_threshold_pct',
            'scope_notes', 'pending_conflict_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_pending_conflict_count(self, obj):
        return obj.conflicts.filter(
            resolution=ResourcePlanConflict.Resolution.PENDING
        ).count()


class ResourcePlanProjectSerializer(serializers.ModelSerializer):
    project_name     = serializers.CharField(
        source='project.display_name', read_only=True
    )
    programme_name   = serializers.CharField(
        source='project.programme_name', read_only=True
    )
    effective_priority   = serializers.CharField(read_only=True)
    effective_confidence = serializers.CharField(read_only=True)

    class Meta:
        model  = ResourcePlanProject
        fields = [
            'id', 'plan', 'project', 'project_name', 'programme_name',
            'basis', 'custom_amount', 'days_required',
            'priority_override', 'confidence_override',
            'effective_priority', 'effective_confidence',
            'dates_strict', 'notes',
        ]
        read_only_fields = ['days_required']


class ResourcePlanProjectTeamSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    allocated_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True
    )

    class Meta:
        model  = ResourcePlanProjectTeam
        fields = [
            'id', 'plan_project', 'team', 'team_name',
            'allocation_type', 'allocation_value', 'allocated_days',
            'sequence_order', 'notes',
        ]


class ResourcePlanPhaseSerializer(serializers.ModelSerializer):
    sprint_range = serializers.ListField(child=serializers.IntegerField(), read_only=True)

    class Meta:
        model  = ResourcePlanPhase
        fields = [
            'id', 'plan_project_team', 'name', 'sequence_order',
            'start_sprint', 'end_sprint',
            'predecessor_phase', 'dependency_type',
            'ramp_pattern', 'max_days_per_sprint',
            'sprint_range', 'notes',
        ]


class ResourcePlanPhaseDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model  = ResourcePlanPhaseDependency
        fields = ['id', 'from_phase', 'to_phase', 'dependency_type']


class ResourcePlanAssignmentSerializer(serializers.ModelSerializer):
    display_name    = serializers.CharField(read_only=True)
    member_name     = serializers.CharField(
        source='team_member.display_name', read_only=True
    )
    assignment_type_display = serializers.CharField(
        source='get_assignment_type_display', read_only=True
    )

    class Meta:
        model  = ResourcePlanAssignment
        fields = [
            'id', 'phase', 'team_member', 'member_name', 'placeholder_name',
            'display_name', 'assignment_type', 'assignment_type_display',
            'is_interim', 'replaces_assignment',
            'pause_from_sprint', 'resume_at_sprint',
            'notes',
        ]


class ResourcePlanAssignmentCellSerializer(serializers.ModelSerializer):
    sprint_name   = serializers.CharField(source='sprint.name', read_only=True)
    sprint_number = serializers.IntegerField(source='sprint.sprint_number', read_only=True)

    class Meta:
        model  = ResourcePlanAssignmentCell
        fields = [
            'id', 'assignment', 'sprint', 'sprint_name', 'sprint_number',
            'days_allocated', 'is_auto', 'is_locked',
        ]
        read_only_fields = ['is_locked']


class ResourcePlanSprintBudgetSerializer(serializers.ModelSerializer):
    sprint_name = serializers.CharField(source='sprint.name', read_only=True)

    class Meta:
        model  = ResourcePlanSprintBudget
        fields = ['id', 'plan_project', 'sprint', 'sprint_name', 'budget_amount', 'notes']


class ResourcePlanConflictSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ResourcePlanConflict
        fields = [
            'id', 'plan', 'conflict_type', 'severity',
            'affected_assignment', 'affected_sprint',
            'description', 'resolution', 'resolved_at', 'created_at',
        ]
        read_only_fields = ['created_at']