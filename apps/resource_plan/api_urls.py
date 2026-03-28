from rest_framework.routers import DefaultRouter
from django.urls import path

from .api_views import (
    ResourcePlanViewSet,
    ResourcePlanCellViewSet,
    ResourcePlanConflictViewSet,
)

router = DefaultRouter()
router.register(r'resource-plans',    ResourcePlanViewSet,   basename='resource-plan')
router.register(r'resource-conflicts', ResourcePlanConflictViewSet, basename='resource-conflict')

# Cell update uses a custom URL pattern (not a standard router route)
urlpatterns = router.urls + [
    path(
        'resource-plan-cells/<int:assignment_pk>/<int:sprint_pk>/',
        ResourcePlanCellViewSet.as_view({'patch': 'partial_update'}),
        name='resource-plan-cell-update',
    ),
]