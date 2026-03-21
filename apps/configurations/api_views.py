from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .services import ConfigurationService
from .serializers import ConfigurationSerializer


class ConfigurationViewSet(viewsets.ViewSet):
    def list(self, request):
        filters = {'search': request.query_params.get('search')}
        configs = ConfigurationService.list_configs(filters=filters)
        return Response(ConfigurationSerializer(configs, many=True).data)

    def retrieve(self, request, pk=None):
        config = ConfigurationService.get_config(pk)
        return Response(ConfigurationSerializer(config).data)

    def create(self, request):
        # serializer = ConfigurationSerializer(data=request.data)
        # serializer.is_valid(raise_exception=True)
        # config = ConfigurationService.create_config(serializer.validated_data)
        # return Response(ConfigurationSerializer(config).data, status=status.HTTP_201_CREATED)
        return Response(
            {'detail': 'Configurations are system-managed and cannot be created via API.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # def update(self, request, pk=None):
    #     serializer = ConfigurationSerializer(data=request.data, partial=True)
    #     serializer.is_valid(raise_exception=True)
    #     config = ConfigurationService.update_config(pk, serializer.validated_data)
    #     return Response(ConfigurationSerializer(config).data)

    def partial_update(self, request, pk=None):
        value = request.data.get('value')
        if value is None:
            return Response(
                {'detail': 'Only the "value" field can be updated.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        config = ConfigurationService.update_config(pk, value)
        return Response(ConfigurationSerializer(config).data)

    def destroy(self, request, pk=None):
        # ConfigurationService.delete_config(pk)
        # return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {'detail': 'Configurations are system-managed and cannot be deleted.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=['get'], url_path='by_code')
    def by_code(self, request):
        code = request.query_params.get('code', '').strip().upper()
        if not code:
            return Response(
                {'detail': 'Provide ?code=YOUR_CODE in the query string.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        config = ConfigurationService.get_by_code(code)
        return Response(ConfigurationSerializer(config).data)
    
    @action(detail=True, methods=['post'], url_path='reset')
    def reset(self, request, pk=None):
        config = ConfigurationService.reset_to_default(pk)
        return Response(ConfigurationSerializer(config).data)
