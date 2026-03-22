from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .services import BudgetService
from .serializers import BudgetSerializer


class BudgetViewSet(viewsets.ViewSet):
    def list(self, request):
        fy_pk      = request.query_params.get('fy')
        project_pk = request.query_params.get('project')
        programme  = request.query_params.get('programme')
        search     = request.query_params.get('search')
        budgets = BudgetService.list_budgets(
            financial_year_id = int(fy_pk)      if fy_pk      else None,
            project_id        = int(project_pk) if project_pk else None,
            programme         = programme        or None,
            search            = search           or None,
        )
        return Response(BudgetSerializer(budgets, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            budget = BudgetService.get_budget(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Budget not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(BudgetSerializer(budget).data)

    def create(self, request):
        serializer = BudgetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            vd     = serializer.validated_data
            budget = BudgetService.create_budget({
                'project_id':        vd['project'].pk,
                'financial_year_id': vd['financial_year'].pk,
                'budget_allocated':  vd.get('budget_allocated'),
                'refined_budget':    vd.get('refined_budget'),
                'notes':             vd.get('notes', ''),
            })
        except ValidationError as exc:
            return Response(
                {'detail': exc.message_dict if hasattr(exc, 'message_dict') else exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(BudgetSerializer(budget).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        try:
            budget = BudgetService.get_budget(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Budget not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = BudgetSerializer(budget, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        update_data = {}
        if 'budget_allocated' in vd: update_data['budget_allocated'] = vd['budget_allocated']
        if 'refined_budget'   in vd: update_data['refined_budget']   = vd['refined_budget']
        if 'notes'            in vd: update_data['notes']            = vd['notes']
        try:
            updated = BudgetService.update_budget(pk, update_data)
        except ValidationError as exc:
            return Response(
                {'detail': exc.message_dict if hasattr(exc, 'message_dict') else exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(BudgetSerializer(updated).data)

    def destroy(self, request, pk=None):
        try:
            BudgetService.delete_budget(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Budget not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='programme-summary')
    def programme_summary(self, request):
        fy_pk = request.query_params.get('fy')
        data  = BudgetService.programme_summary(
            financial_year_id=int(fy_pk) if fy_pk else None
        )
        return Response(data)

    @action(detail=False, methods=['post'], url_path='seed')
    def seed(self, request):
        fy_pk = request.query_params.get('fy')
        if not fy_pk:
            return Response({'detail': '"fy" query param required.'}, status=400)
        created = BudgetService.seed_for_all_projects(int(fy_pk))
        return Response({'created': created})