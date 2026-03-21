from django.contrib import admin
from .models import Team

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display  = ['name', 'is_active']
    list_filter   = ['is_active']
    search_fields = ['name']
