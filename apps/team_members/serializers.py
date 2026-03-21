from rest_framework import serializers
from .models import TeamMember, TeamMemberHistory


class TeamMemberSerializer(serializers.ModelSerializer):
    skill_ids      = serializers.PrimaryKeyRelatedField(
        source='skills', many=True, read_only=True
    )
    team_name      = serializers.CharField(
        source='team.name', read_only=True, default=None
    )
    role_display   = serializers.CharField(
        source='get_role_display', read_only=True
    )
    location_display = serializers.CharField(
        source='get_location_display', read_only=True
    )
    employee_type_display = serializers.CharField(
        source='get_employee_type_display', read_only=True
    )

    class Meta:
        model  = TeamMember
        fields = [
            'id',
            'first_name', 'last_name', 'display_name', 'full_name',
            'role', 'role_display',
            'location', 'location_display',
            'employee_type', 'employee_type_display',
            'team', 'team_name',
            'skill_ids',
            'start_date', 'end_date',
            'default_holidays',
            'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['display_name', 'full_name', 'created_at', 'updated_at']

    def validate_default_holidays(self, value):
        if value < 0:
            raise serializers.ValidationError('Holidays cannot be negative.')
        if value > 365:
            raise serializers.ValidationError('Holidays cannot exceed 365 days.')
        return value

    def validate(self, attrs):
        start = attrs.get('start_date')
        end   = attrs.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError(
                {'end_date': 'End date cannot be before start date.'}
            )
        return attrs


class TeamMemberHistorySerializer(serializers.ModelSerializer):
    from_team_name = serializers.CharField(
        source='from_team.name', read_only=True, default=None
    )
    to_team_name = serializers.CharField(
        source='to_team.name', read_only=True, default=None
    )
    member_name = serializers.CharField(
        source='member.display_name', read_only=True
    )

    class Meta:
        model  = TeamMemberHistory
        fields = [
            'id', 'member', 'member_name',
            'from_team', 'from_team_name',
            'to_team',   'to_team_name',
            'moved_on', 'note', 'created_at',
        ]
        read_only_fields = ['created_at']


class MoveTeamSerializer(serializers.Serializer):
    to_team_id = serializers.IntegerField(allow_null=True, required=False)
    moved_on   = serializers.DateField()
    note       = serializers.CharField(required=False, allow_blank=True, default='')