from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .services import ProjectService
from .serializers import ProjectSerializer, ProjectCommentSerializer


class ProjectViewSet(viewsets.ViewSet):
    def list(self, request):
        filters = {
            'search':           request.query_params.get('search'),
            'status':           request.query_params.get('status'),
            'assigned_team_id': request.query_params.get('assigned_team_id'),
            'confidence':       request.query_params.get('confidence'),
            'priority':         request.query_params.get('priority'),
        }
        projects = ProjectService.list_projects(filters=filters)
        return Response(ProjectSerializer(projects, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            project = ProjectService.get_project(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectSerializer(project).data)

    def create(self, request):
        serializer = ProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data['collaborator_ids'] = [t.pk for t in data.pop('collaborators', [])]
        if data.get('assigned_team'):
            data['assigned_team_id'] = data.pop('assigned_team').pk
        try:
            project = ProjectService.create_project(data)
        except ValidationError as exc:
            return Response(
                {'detail': exc.message_dict if hasattr(exc, 'message_dict') else exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        serializer = ProjectSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data['collaborator_ids'] = [t.pk for t in data.pop('collaborators', [])]
        if 'assigned_team' in data:
            t = data.pop('assigned_team')
            data['assigned_team_id'] = t.pk if t else None
        try:
            project = ProjectService.update_project(pk, data)
        except ObjectDoesNotExist:
            return Response({'detail': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response(
                {'detail': exc.message_dict if hasattr(exc, 'message_dict') else exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ProjectSerializer(project).data)

    def destroy(self, request, pk=None):
        try:
            ProjectService.delete_project(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='sub_statuses')
    def sub_statuses(self, request):
        s = request.query_params.get('status', '').upper()
        if s:
            return Response({'status': s, 'sub_statuses': ProjectService.get_sub_statuses(s)})
        return Response(ProjectService.all_sub_statuses())

    @action(detail=True, methods=['get'], url_path='comments')
    def comments(self, request, pk=None):
        try:
            ProjectService.get_project(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)
        comments = ProjectService.get_comments(pk)
        return Response(ProjectCommentSerializer(comments, many=True).data)

    @action(detail=True, methods=['post'], url_path='add_comment')
    def add_comment(self, request, pk=None):
        body   = request.data.get('body', '')
        author = request.data.get('author', '')
        try:
            comment = ProjectService.add_comment(pk, body, author)
        except ObjectDoesNotExist:
            return Response({'detail': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ProjectCommentSerializer(comment).data, status=status.HTTP_201_CREATED)