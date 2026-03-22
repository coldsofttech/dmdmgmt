from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .services import FinancialYearService
from .serializers import FinancialYearSerializer


class FinancialYearViewSet(viewsets.ViewSet):
    def list(self, request):
        fys = FinancialYearService.list_financial_years()
        return Response(FinancialYearSerializer(fys, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            fy = FinancialYearService.get_financial_year(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Financial year not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(FinancialYearSerializer(fy).data)

    def create(self, request):
        serializer = FinancialYearSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            fy = FinancialYearService.create_financial_year(serializer.validated_data)
        except ValidationError as exc:
            return Response(
                {'detail': exc.message_dict if hasattr(exc, 'message_dict') else exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(FinancialYearSerializer(fy).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        serializer = FinancialYearSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            fy = FinancialYearService.update_financial_year(pk, serializer.validated_data)
        except ObjectDoesNotExist:
            return Response({'detail': 'Financial year not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response(
                {'detail': exc.message_dict if hasattr(exc, 'message_dict') else exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(FinancialYearSerializer(fy).data)

    def destroy(self, request, pk=None):
        try:
            FinancialYearService.delete_financial_year(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Financial year not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='set_active')
    def set_active(self, request, pk=None):
        try:
            fy = FinancialYearService.set_active(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Financial year not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(FinancialYearSerializer(fy).data)

    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        fy = FinancialYearService.get_active()
        if not fy:
            return Response({'detail': 'No active financial year set.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(FinancialYearSerializer(fy).data)