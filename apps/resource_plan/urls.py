from django.urls import path
from . import views

app_name = 'resource_plan'

urlpatterns = [
    path('',
         views.ResourcePlanListView.as_view(),
         name='list'),

    path('new/',
         views.ResourcePlanCreateView.as_view(),
         name='create'),

    path('<int:pk>/',
         views.ResourcePlanDetailView.as_view(),
         name='detail'),

    path('<int:pk>/edit/',
         views.ResourcePlanUpdateView.as_view(),
         name='edit'),

    path('<int:pk>/configure/',
         views.ResourcePlanConfigureView.as_view(),
         name='configure'),

    path('<int:pk>/delete/',
         views.ResourcePlanDeleteView.as_view(),
         name='delete'),

    path('<int:plan_pk>/cell/<int:assignment_pk>/<int:sprint_pk>/',
         views.ResourcePlanCellUpdateView.as_view(),
         name='cell_update'),

    path('<int:pk>/generate-placeholders/',
         views.ResourcePlanGeneratePlaceholdersView.as_view(),
         name='generate_placeholders'),
]