from django.urls import path
from . import views

app_name = 'resource_plan'

urlpatterns = [
    # ── Plan CRUD ─────────────────────────────────────────
    path('',         views.ResourcePlanListView.as_view(),    name='list'),
    path('new/',     views.ResourcePlanCreateView.as_view(),  name='create'),
    path('<int:pk>/',views.ResourcePlanDetailView.as_view(),  name='detail'),
    path('<int:pk>/edit/',      views.ResourcePlanUpdateView.as_view(),  name='edit'),
    path('<int:pk>/configure/', views.ResourcePlanConfigureView.as_view(), name='configure'),
    path('<int:pk>/delete/',    views.ResourcePlanDeleteView.as_view(),  name='delete'),
    path('<int:plan_pk>/cell/<int:assignment_pk>/<int:sprint_pk>/',
         views.ResourcePlanCellUpdateView.as_view(), name='cell_update'),
    path('<int:pk>/generate-placeholders/',
         views.ResourcePlanGeneratePlaceholdersView.as_view(), name='generate_placeholders'),

    # ── Round A: Separate project config screen ────────────
    path('<int:pk>/projects/',
         views.ResourcePlanProjectsView.as_view(), name='projects'),
    path('<int:plan_pk>/projects/<int:pp_pk>/edit/',
         views.ResourcePlanProjectEditView.as_view(), name='project_edit'),
    path('<int:plan_pk>/projects/<int:pp_pk>/delete/',
         views.ResourcePlanProjectDeleteView.as_view(), name='project_delete'),

    # ── Round A: Phase CRUD ────────────────────────────────
    path('<int:plan_pk>/phases/<int:phase_pk>/edit/',
         views.ResourcePlanPhaseEditView.as_view(), name='phase_edit'),
    path('<int:plan_pk>/phases/<int:phase_pk>/delete/',
         views.ResourcePlanPhaseDeleteView.as_view(), name='phase_delete'),

    # ── Round A: Assignment CRUD ───────────────────────────
    path('<int:plan_pk>/phases/<int:phase_pk>/assignments/',
         views.ResourcePlanAssignmentListView.as_view(), name='assignment_list'),
    path('<int:plan_pk>/phases/<int:phase_pk>/assignments/new/',
         views.ResourcePlanAssignmentCreateView.as_view(), name='assignment_create'),
    path('<int:plan_pk>/assignments/<int:assignment_pk>/edit/',
         views.ResourcePlanAssignmentEditView.as_view(), name='assignment_edit'),
    path('<int:plan_pk>/assignments/<int:assignment_pk>/delete/',
         views.ResourcePlanAssignmentDeleteView.as_view(), name='assignment_delete'),

    # ── Round A: Placeholder leave view / edit ─────────────
    path('<int:pk>/placeholders/',
         views.ResourcePlanPlaceholdersView.as_view(), name='placeholders'),
    path('<int:plan_pk>/placeholders/new/',
         views.ResourcePlanPlaceholderCreateView.as_view(), name='placeholder_create'),
    path('<int:plan_pk>/placeholders/<int:ph_pk>/update/',
         views.ResourcePlanPlaceholderUpdateView.as_view(), name='placeholder_update'),
    path('<int:plan_pk>/placeholders/<int:ph_pk>/delete/',
         views.ResourcePlanPlaceholderDeleteView.as_view(), name='placeholder_delete'),
]