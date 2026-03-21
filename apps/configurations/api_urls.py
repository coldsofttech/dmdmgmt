from rest_framework.routers import DefaultRouter
from .api_views import ConfigurationViewSet

router = DefaultRouter()
router.register(r'configs', ConfigurationViewSet, basename='configuration')
urlpatterns = router.urls
