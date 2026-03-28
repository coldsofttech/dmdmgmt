from django.urls import path
from . import views

app_name = 'sprints'

urlpatterns = [
    path('', views.SprintListView.as_view(), name='list'),
    path('new/', views.SprintCreateView.as_view(), name='create'),
    path('<int:pk>/', views.SprintDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.SprintUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.SprintDeleteView.as_view(), name='delete'),
    path('delete-fy/', views.SprintDeleteFYView.as_view(), name='delete_fy'),
]