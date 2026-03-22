from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    # path('',                    views.ProjectListView.as_view(),   name='list'),
    # path('new/',                views.ProjectCreateView.as_view(), name='create'),
    # path('<int:pk>/',           views.ProjectDetailView.as_view(), name='detail'),
    # path('<int:pk>/edit/',      views.ProjectUpdateView.as_view(), name='edit'),
    # path('sub_statuses/',       views.SubStatusApiView.as_view(),  name='sub_statuses'),
    path('', views.ProjectListView.as_view(), name='list'),
    path('view/new/', views.NewProjectListView.as_view(), name='list_new'),
    path('view/in-progress/', views.InProgressProjectListView.as_view(), name='list_in_progress'),
    path('view/completed/', views.CompletedProjectListView.as_view(), name='list_completed'),
    path('view/cancelled/', views.CancelledProjectListView.as_view(), name='list_cancelled'),
    path('view/bau/', views.BAUProjectListView.as_view(), name='list_bau'),
    path('view/maintenance/', views.MaintenanceProjectListView.as_view(), name='list_maintenance'),
    path('new/', views.ProjectCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='edit'),
    path('<int:pk>/code-history/', views.CodeHistoryView.as_view(), name='code_history'),
    path('<int:pk>/estimate-history/', views.EstimateHistoryView.as_view(), name='estimate_history'),
    path('<int:pk>/comments/<int:comment_pk>/edit/', views.CommentEditView.as_view(), name='comment_edit'),
    path('<int:pk>/comments/<int:comment_pk>/delete/', views.CommentDeleteView.as_view(), name='comment_delete'),
    path('sub_statuses/', views.SubStatusApiView.as_view(), name='sub_statuses'),
]