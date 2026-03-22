from rest_framework.routers import DefaultRouter
from .api_views import FinancialYearViewSet

router = DefaultRouter()
router.register(r'financial-years', FinancialYearViewSet, basename='financial-year')
urlpatterns = router.urls
