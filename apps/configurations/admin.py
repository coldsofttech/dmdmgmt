from django.contrib import admin
from django.contrib import messages as django_messages
from .services import ConfigurationService
from .models import Configuration


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display    = ['code', 'label', 'value', 'description', 'created_at', 'updated_at']
    search_fields   = ['code', 'label', 'description']
    readonly_fields = ['code', 'label', 'description', 'created_at', 'updated_at']
    ordering        = ['code']
    actions         = ['reset_to_defaults']

    def has_delete_permission(self, request, obj=None):
        # return True
        return False
    
    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        return ['code', 'label', 'description', 'created_at', 'updated_at']
        # if obj:
            # return ['code', 'label', 'description', 'created_at', 'updated_at']
        # return ['created_at', 'updated_at']

    @admin.action(description='Reset selected configurations to factory defaults')
    def reset_to_defaults(self, request, queryset):
        reset_count  = 0
        skipped      = []
        for config in queryset:
            try:
                ConfigurationService.reset_to_default(config.pk)
                reset_count += 1
            except Exception:
                skipped.append(config.code)
 
        if reset_count:
            self.message_user(
                request,
                f'{reset_count} configuration(s) reset to factory defaults.',
                django_messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f'No factory default registered for: {", ".join(skipped)}.',
                django_messages.WARNING,
            )
