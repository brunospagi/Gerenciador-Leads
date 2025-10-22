from django.contrib import admin
from .models import TVVideo

class TVVideoAdmin(admin.ModelAdmin):
    # Enforce the singleton pattern in the admin interface (disable 'Add' button if exists)
    def has_add_permission(self, request):
        return not TVVideo.objects.exists()

    # Disable delete permission (to ensure the single entry is always present)
    def has_delete_permission(self, request, obj=None):
        return False
    
    list_display = ('titulo', 'last_updated')
    fields = ('titulo', 'video_url')

admin.site.register(TVVideo, TVVideoAdmin)