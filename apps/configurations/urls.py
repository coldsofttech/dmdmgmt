from django.urls import path
from . import views

app_name = 'configurations'

urlpatterns = [
    path('',               views.ConfigurationListView.as_view(),   name='list'),
    # path('new/',           views.ConfigurationCreateView.as_view(), name='create'),
    path('<int:pk>/',      views.ConfigurationDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.ConfigurationUpdateView.as_view(), name='edit'),
    path('<int:pk>/reset/', views.ConfigurationResetView.as_view(), name='reset'),
    # path('export/',        views.ConfigurationExportView.as_view(), name='export'),
]