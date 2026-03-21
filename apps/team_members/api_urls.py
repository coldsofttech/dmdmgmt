from rest_framework.routers import DefaultRouter
from .api_views import TeamMemberViewSet

router = DefaultRouter()
router.register(r'members', TeamMemberViewSet, basename='team-member')
urlpatterns = router.urls