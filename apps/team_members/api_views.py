import datetime
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from .services import TeamMemberService
from .serializers import (
    TeamMemberSerializer,
    TeamMemberHistorySerializer,
    MoveTeamSerializer,
)


class TeamMemberViewSet(viewsets.ViewSet):
    def list(self, request):
        filters = {
            'search':        request.query_params.get('search'),
            'team_id':       request.query_params.get('team_id'),
            'role':          request.query_params.get('role'),
            'location':      request.query_params.get('location'),
            'employee_type': request.query_params.get('employee_type'),
            'skill_id':      request.query_params.get('skill_id'),
        }
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            filters['is_active'] = is_active.lower() == 'true'

        members = TeamMemberService.list_members(filters=filters)
        return Response(TeamMemberSerializer(members, many=True).data)

    def retrieve(self, request, pk=None):
        member = TeamMemberService.get_member(pk)
        return Response(TeamMemberSerializer(member).data)

    def create(self, request):
        serializer = TeamMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data['skill_ids'] = [s.id for s in data.pop('skills', [])]
        data['team_id']   = data.pop('team').pk if data.get('team') else None
        member = TeamMemberService.create_member(data)
        return Response(
            TeamMemberSerializer(member).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, pk=None):
        serializer = TeamMemberSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data['skill_ids'] = [s.id for s in data.pop('skills', [])]
        if 'team' in data:
            data['team_id'] = data.pop('team').pk if data['team'] else None

        member = TeamMemberService.update_member(pk, data)
        return Response(TeamMemberSerializer(member).data)

    def destroy(self, request, pk=None):
        TeamMemberService.delete_member(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        TeamMemberService.get_member(pk)
        history = TeamMemberService.get_team_history(pk)
        return Response(TeamMemberHistorySerializer(history, many=True).data)

    @action(detail=True, methods=['post'], url_path='move_team')
    def move_team(self, request, pk=None):
        serializer = MoveTeamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        member = TeamMemberService.move_to_team(
                member_id  = pk,
                to_team_id = d.get('to_team_id'),
                moved_on   = d['moved_on'],
                note       = d.get('note', ''),
            )
        return Response(TeamMemberSerializer(member).data)