from rest_framework.routers import DefaultRouter
from .api_views import HolidayViewSet

router = DefaultRouter()
router.register(r'holidays', HolidayViewSet, basename='holiday')
urlpatterns = router.urls