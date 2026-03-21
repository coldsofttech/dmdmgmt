from django.contrib import admin
from .models import Skill


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display   = ['skill', 'description', 'is_active', 'created_at', 'updated_at']
    list_filter    = ['is_active']
    search_fields  = ['skill', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering       = ['skill']
