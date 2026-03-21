from django.urls import path
from . import views

app_name = 'teams'

urlpatterns = [
    path('',              views.TeamListView.as_view(),   name='list'),
    path('new/',          views.TeamCreateView.as_view(), name='create'),
    path('<int:pk>/',     views.TeamDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/',views.TeamUpdateView.as_view(), name='edit'),
    # path('export/',       views.TeamExportView.as_view(), name='export'),
]
