from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .services import HolidayService
from .serializers import HolidaySerializer


class HolidayViewSet(viewsets.ViewSet):
    def list(self, request):
        fy_pk    = request.query_params.get('fy')
        holidays = HolidayService.list_holidays(
            financial_year_id=int(fy_pk) if fy_pk else None
        )
        return Response(HolidaySerializer(holidays, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            holiday = HolidayService.get_holiday(pk)
        except ObjectDoesNotExist:
            return Response(
                {'detail': 'Holiday not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(HolidaySerializer(holiday).data)

    def create(self, request):
        serializer = HolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            holiday = HolidayService.create_holiday({
                'financial_year_id': serializer.validated_data['financial_year'].pk,
                'holiday_date':      serializer.validated_data['holiday_date'],
                'note':              serializer.validated_data.get('note', ''),
            })
        except ValidationError as exc:
            return Response(
                {'detail': exc.message_dict if hasattr(exc, 'message_dict') else exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            HolidaySerializer(holiday).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, pk=None):
        try:
            holiday = HolidayService.get_holiday(pk)
        except ObjectDoesNotExist:
            return Response(
                {'detail': 'Holiday not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = HolidaySerializer(holiday, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        update_data = {}
        vd = serializer.validated_data
        if 'financial_year' in vd:
            update_data['financial_year_id'] = vd['financial_year'].pk
        if 'holiday_date' in vd:
            update_data['holiday_date'] = vd['holiday_date']
        if 'note' in vd:
            update_data['note'] = vd['note']

        try:
            updated = HolidayService.update_holiday(pk, update_data)
        except ValidationError as exc:
            return Response(
                {'detail': exc.message_dict if hasattr(exc, 'message_dict') else exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(HolidaySerializer(updated).data)

    def destroy(self, request, pk=None):
        try:
            HolidayService.delete_holiday(pk)
        except ObjectDoesNotExist:
            return Response(
                {'detail': 'Holiday not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as exc:
            return Response(
                {'detail': exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='by_fy')
    def by_fy(self, request):
        fy_pk = request.query_params.get('fy')
        if not fy_pk:
            return Response(
                {'detail': 'Query parameter "fy" is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            holidays = HolidayService.list_holidays(financial_year_id=int(fy_pk))
        except (ValueError, TypeError):
            return Response(
                {'detail': '"fy" must be a valid integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(HolidaySerializer(holidays, many=True).data)