"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.teams.api_views import TeamViewSet
from apps.skills.api_views import SkillViewSet
from apps.configurations.api_views import ConfigurationViewSet
from apps.team_members.api_views import TeamMemberViewSet
from apps.projects.api_views import ProjectViewSet
from apps.financial_years.api_views import FinancialYearViewSet
from apps.holidays.api_views import HolidayViewSet
from apps.leaves.api_views import LeaveViewSet
from apps.budgets.api_views import BudgetViewSet
from apps.sprints.api_views import SprintViewSet

router = DefaultRouter()
router.register(r'teams', TeamViewSet, basename='team')
router.register(r'skills', SkillViewSet, basename='skill')
router.register(r'configs', ConfigurationViewSet, basename='configuration')
router.register(r'members', TeamMemberViewSet, basename='team-member')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'financial-years', FinancialYearViewSet, basename='financial-year')
router.register(r'holidays', HolidayViewSet, basename='holiday')
router.register(r'leaves', LeaveViewSet, basename='leave')
router.register(r'budgets', BudgetViewSet, basename='budget')
router.register(r'sprints', SprintViewSet, basename='sprint')

urlpatterns = [
    path('admin/', admin.site.urls),

    # REST API
    path('api/v1/', include(router.urls)),

    # Manage
    path('teams/', include('apps.teams.urls')),
    path('members/', include('apps.team_members.urls')),
    path('projects/', include('apps.projects.urls')),
    path('financial-years/', include('apps.financial_years.urls')),
    path('holidays/', include('apps.holidays.urls')),
    path('budgets/', include('apps.budgets.urls')),

    # Plan
    path('leaves/', include('apps.leaves.urls')),
    path('sprints/', include('apps.sprints.urls')),

    # Config / Settings
    path('settings/skills/', include('apps.skills.urls')),
    path('settings/config/', include('apps.configurations.urls')),
    
    path('', include('apps.teams.urls'))
]
