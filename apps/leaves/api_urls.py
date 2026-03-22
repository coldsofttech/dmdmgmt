from rest_framework.routers import DefaultRouter
from .api_views import LeaveViewSet

router = DefaultRouter()
router.register(r'leaves', LeaveViewSet, basename='leave')
urlpatterns = router.urls