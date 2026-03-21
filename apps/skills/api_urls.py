from rest_framework.routers import DefaultRouter
from .api_views import SkillViewSet

router = DefaultRouter()
router.register(r'skills', SkillViewSet, basename='skill')
urlpatterns = router.urls
