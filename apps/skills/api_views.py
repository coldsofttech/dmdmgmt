from rest_framework import viewsets, status
from rest_framework.response import Response
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from .services import SkillService
from .serializers import SkillSerializer


class SkillViewSet(viewsets.ViewSet):
    def list(self, request):
        skills = SkillService.list_skills(filters=request.query_params)
        return Response(SkillSerializer(skills, many=True).data)

    def retrieve(self, request, pk=None):
        skill = SkillService.get_skill(pk)
        return Response(SkillSerializer(skill).data)

    def create(self, request):
        serializer = SkillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team = SkillService.create_skill(serializer.validated_data)
        return Response(SkillSerializer(team).data, status=status.HTTP_201_CREATED)
    
    def update(self, request, pk=None):
        serializer = SkillSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        team = SkillService.update_skill(pk, serializer.validated_data)
        return Response(SkillSerializer(team).data)

    def destroy(self, request, pk=None):
        SkillService.delete_skill(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
