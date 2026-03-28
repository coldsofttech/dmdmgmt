from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .services import SprintService
from .serializers import SprintSerializer


class SprintViewSet(viewsets.ViewSet):
    def list(self, request):
        fy_pk   = request.query_params.get('fy')
        sprints = SprintService.list_sprints(
            financial_year_id=int(fy_pk) if fy_pk else None
        )
        return Response(SprintSerializer(sprints, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            sprint = SprintService.get_sprint(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Sprint not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SprintSerializer(sprint).data)

    def create(self, request):
        serializer = SprintSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            vd     = serializer.validated_data
            sprint = SprintService.create_sprint({
                'financial_year_id': vd['financial_year'].pk,
                'sprint_number':     vd['sprint_number'],
                'name':              vd['name'],
                'start_date':        vd['start_date'],
                'end_date':          vd['end_date'],
                'notes':             vd.get('notes', ''),
            })
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SprintSerializer(sprint).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        try:
            sprint = SprintService.get_sprint(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Sprint not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SprintSerializer(sprint, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        update_data = {}
        if 'sprint_number' in vd: update_data['sprint_number'] = vd['sprint_number']
        if 'name'          in vd: update_data['name']          = vd['name']
        if 'start_date'    in vd: update_data['start_date']    = vd['start_date']
        if 'end_date'      in vd: update_data['end_date']      = vd['end_date']
        if 'notes'         in vd: update_data['notes']         = vd['notes']
        try:
            updated = SprintService.update_sprint(pk, update_data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SprintSerializer(updated).data)

    def destroy(self, request, pk=None):
        try:
            SprintService.delete_sprint(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Sprint not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        fy_pk = request.data.get('financial_year')
        start = request.data.get('first_sprint_start')
        if not fy_pk or not start:
            return Response(
                {'detail': 'financial_year and first_sprint_start are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            import datetime
            if isinstance(start, str):
                start = datetime.date.fromisoformat(start)
            sprints = SprintService.generate_sprints(int(fy_pk), start)
        except ValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'created': len(sprints),
            'sprints': SprintSerializer(sprints, many=True).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['delete'], url_path='delete-fy')
    def delete_fy(self, request):
        fy_pk = request.query_params.get('fy')
        if not fy_pk:
            return Response({'detail': '"fy" param required.'}, status=400)
        deleted = SprintService.delete_all_for_fy(int(fy_pk))
        return Response({'deleted': deleted})

    @action(detail=True, methods=['get'])
    def capacity(self, request, pk=None):
        try:
            sprint = SprintService.get_sprint(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Sprint not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SprintService.sprint_capacity(sprint))

    @action(detail=False, methods=['get'])
    def consistency(self, request):
        fy_pk = request.query_params.get('fy')
        if not fy_pk:
            return Response({'detail': '"fy" param required.'}, status=400)
        return Response(SprintService.check_consistency(int(fy_pk)))