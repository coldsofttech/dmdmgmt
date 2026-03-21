from rest_framework.routers import DefaultRouter
from .api_views import TeamViewSet

router = DefaultRouter()
router.register(r'teams', TeamViewSet, basename='team')
urlpatterns = router.urls
