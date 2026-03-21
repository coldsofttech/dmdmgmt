from django.urls import path
from . import views

app_name = 'team_members'

urlpatterns = [
    path('', views.TeamMemberListView.as_view(), name='list'),
    path('new/', views.TeamMemberCreateView.as_view(), name='create'),
    path('<int:pk>/', views.TeamMemberDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.TeamMemberUpdateView.as_view(), name='edit'),
    path('<int:pk>/move/', views.TeamMemberMoveView.as_view(), name='move'),
]