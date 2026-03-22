from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .services import LeaveService
from .serializers import LeaveSerializer


class LeaveViewSet(viewsets.ViewSet):
    def list(self, request):
        fy_pk     = request.query_params.get('fy')
        member_pk = request.query_params.get('member')
        team_pk   = request.query_params.get('team')
        leaves = LeaveService.list_leaves(
            financial_year_id = int(fy_pk)     if fy_pk     else None,
            team_member_id    = int(member_pk) if member_pk else None,
            team_id           = int(team_pk)   if team_pk   else None,
        )
        return Response(LeaveSerializer(leaves, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            leave = LeaveService.get_leave(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Leave not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(LeaveSerializer(leave).data)

    def create(self, request):
        serializer = LeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            vd    = serializer.validated_data
            leave = LeaveService.create_leave({
                'team_member_id':   vd['team_member'].pk,
                'financial_year_id': vd['financial_year'].pk,
                'start_date':       vd['start_date'],
                'end_date':         vd['end_date'],
                'note':             vd.get('note', ''),
            })
        except ValidationError as exc:
            return Response(
                {'detail': exc.message_dict if hasattr(exc, 'message_dict') else exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(LeaveSerializer(leave).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        return self._do_update(request, pk)

    def partial_update(self, request, pk=None):
        return self._do_update(request, pk, partial=True)

    def _do_update(self, request, pk, partial=False):
        try:
            leave = LeaveService.get_leave(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Leave not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = LeaveSerializer(leave, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        update_data = {}
        if 'team_member'    in vd: update_data['team_member_id']    = vd['team_member'].pk
        if 'financial_year' in vd: update_data['financial_year_id'] = vd['financial_year'].pk
        if 'start_date'     in vd: update_data['start_date']        = vd['start_date']
        if 'end_date'       in vd: update_data['end_date']          = vd['end_date']
        if 'note'           in vd: update_data['note']              = vd['note']
        try:
            updated = LeaveService.update_leave(pk, update_data)
        except ValidationError as exc:
            return Response(
                {'detail': exc.message_dict if hasattr(exc, 'message_dict') else exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(LeaveSerializer(updated).data)

    def destroy(self, request, pk=None):
        try:
            LeaveService.delete_leave(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Leave not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='by_member')
    def by_member(self, request):
        member_pk = request.query_params.get('member')
        fy_pk     = request.query_params.get('fy')
        if not member_pk:
            return Response({'detail': '"member" query param required.'}, status=400)
        leaves = LeaveService.list_leaves(
            team_member_id    = int(member_pk),
            financial_year_id = int(fy_pk) if fy_pk else None,
        )
        return Response(LeaveSerializer(leaves, many=True).data)

    @action(detail=False, methods=['get'], url_path='by_team')
    def by_team(self, request):
        team_pk = request.query_params.get('team')
        fy_pk   = request.query_params.get('fy')
        if not team_pk:
            return Response({'detail': '"team" query param required.'}, status=400)
        leaves = LeaveService.list_leaves(
            team_id           = int(team_pk),
            financial_year_id = int(fy_pk) if fy_pk else None,
        )
        return Response(LeaveSerializer(leaves, many=True).data)