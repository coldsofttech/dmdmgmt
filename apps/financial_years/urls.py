from django.urls import path
from . import views

app_name = 'financial_years'

urlpatterns = [
    path('', views.FinancialYearListView.as_view(), name='list'),
    path('new/', views.FinancialYearCreateView.as_view(), name='create'),
    path('<int:pk>/', views.FinancialYearDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.FinancialYearUpdateView.as_view(), name='edit'),
    path('<int:pk>/set-active/', views.FinancialYearSetActiveView.as_view(), name='set_active'),
    path('<int:pk>/delete/', views.FinancialYearDeleteView.as_view(), name='delete'),
]