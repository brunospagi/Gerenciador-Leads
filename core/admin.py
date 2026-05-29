from django.contrib import admin
from .models import BannerSistema, AuditLog

@admin.register(BannerSistema)
class BannerSistemaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'ativo', 'usar_imagem')
    list_editable = ('ativo',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "module",
        "action",
        "username_snapshot",
        "method",
        "status_code",
        "success",
        "severity",
    )
    list_filter = ("module", "method", "severity", "success", "created_at")
    search_fields = ("action", "path", "username_snapshot", "object_repr")
    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "user",
        "username_snapshot",
        "nivel_acesso_snapshot",
        "module",
        "action",
        "method",
        "path",
        "status_code",
        "ip_address",
        "user_agent",
        "object_repr",
        "payload",
        "success",
        "severity",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
