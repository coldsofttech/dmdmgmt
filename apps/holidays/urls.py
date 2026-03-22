from django.urls import path
from . import views

app_name = 'holidays'

urlpatterns = [
    path('', views.HolidayListView.as_view(), name='list'),
    path('new/', views.HolidayCreateView.as_view(), name='create'),
    path('<int:pk>/', views.HolidayDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.HolidayUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.HolidayDeleteView.as_view(), name='delete'),
]