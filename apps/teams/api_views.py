from rest_framework import viewsets, status
from rest_framework.response import Response
from .services import TeamService
from .serializers import TeamSerializer

class TeamViewSet(viewsets.ViewSet):
    def list(self, request):
        teams = TeamService.list_teams(filters=request.query_params)
        return Response(TeamSerializer(teams, many=True).data)

    def retrieve(self, request, pk=None):
        team = TeamService.get_team(pk)
        return Response(TeamSerializer(team).data)

    def create(self, request):
        serializer = TeamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team = TeamService.create_team(serializer.validated_data)
        return Response(TeamSerializer(team).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        serializer = TeamSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        team = TeamService.update_team(pk, serializer.validated_data)
        return Response(TeamSerializer(team).data)

    def destroy(self, request, pk=None):
        TeamService.delete_team(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
