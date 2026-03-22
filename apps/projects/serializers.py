from rest_framework import serializers
from .models import Project, ProjectComment


class ProjectCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ProjectComment
        fields = ['id', 'project', 'body', 'author', 'created_at']
        read_only_fields = ['created_at']


class ProjectSerializer(serializers.ModelSerializer):
    assigned_team_name = serializers.CharField(
        source='assigned_team.name', read_only=True, default=None,
    )
    collaborator_ids = serializers.PrimaryKeyRelatedField(
        source='collaborators', many=True, read_only=True,
    )
    collaborator_names = serializers.SerializerMethodField()
    status_display     = serializers.CharField(source='get_status_display',     read_only=True)
    confidence_display = serializers.CharField(source='get_confidence_display', read_only=True)
    priority_display   = serializers.CharField(source='get_priority_display',   read_only=True)
    project_contacts_list = serializers.ListField(source='project_contacts_list', read_only=True)
    finance_contacts_list = serializers.ListField(source='finance_contacts_list', read_only=True)
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model  = Project
        fields = [
            'id',
            'programme_name', 'project_name', 'display_name', 'project_code',
            'project_contacts', 'project_contacts_list',
            'finance_contacts', 'finance_contacts_list',
            'assigned_team', 'assigned_team_name',
            'collaborator_ids', 'collaborator_names',
            'status', 'status_display', 'sub_status',
            'efforts_issued', 'efforts_issue_commitment_date',
            'next_connect_date', 'run_cost_applies',
            'confidence', 'confidence_display',
            'priority', 'priority_display',
            'tentative_start_date', 'tentative_end_date',
            'comment_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['display_name', 'created_at', 'updated_at']

    def get_collaborator_names(self, obj):
        return [t.name for t in obj.collaborators.all()]

    def get_comment_count(self, obj):
        return obj.comments.count()

    def validate(self, attrs):
        status = attrs.get('status', getattr(self.instance, 'status', Project.Status.NEW))
        if status == Project.Status.IN_PROGRESS:
            missing = []
            if not attrs.get('assigned_team', getattr(self.instance, 'assigned_team', None)):
                missing.append('assigned_team')
            if not attrs.get('project_code', getattr(self.instance, 'project_code', '')).strip():
                missing.append('project_code')
            if not attrs.get('confidence', getattr(self.instance, 'confidence', '')):
                missing.append('confidence')
            if not attrs.get('priority', getattr(self.instance, 'priority', '')):
                missing.append('priority')
            if missing:
                raise serializers.ValidationError({
                    'status': (
                        f'To move to In Progress the following fields are required: '
                        f'{", ".join(missing)}.'
                    )
                })
        return attrs