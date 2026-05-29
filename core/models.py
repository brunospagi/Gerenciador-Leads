from django.db import models
from django.conf import settings
from crmspagi.storage_backends import PublicMediaStorage # Sua classe do MinIO

class BannerSistema(models.Model):
    titulo = models.CharField(max_length=100, default="Logo Principal")
    imagem = models.ImageField(
        storage=PublicMediaStorage(), 
        upload_to='sistema/banners/',
        verbose_name="Imagem do Banner/Logo"
    )
    ativo = models.BooleanField(default=True)
    
    # Campo para controlar se usa imagem ou apenas texto
    usar_imagem = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Configuração de Banner"
        verbose_name_plural = "Banners do Sistema"

    def save(self, *args, **kwargs):
        # Garante que apenas 1 banner fique ativo por vez
        if self.ativo:
            BannerSistema.objects.filter(ativo=True).exclude(pk=self.pk).update(ativo=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo


class AuditLog(models.Model):
    SEVERITY_INFO = "INFO"
    SEVERITY_WARN = "WARN"
    SEVERITY_ERROR = "ERROR"
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARN, "Aviso"),
        (SEVERITY_ERROR, "Erro"),
    ]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    username_snapshot = models.CharField(max_length=150, blank=True, default="")
    nivel_acesso_snapshot = models.CharField(max_length=30, blank=True, default="")

    module = models.CharField(max_length=80, db_index=True)
    action = models.CharField(max_length=160, db_index=True)
    method = models.CharField(max_length=10, blank=True, default="")
    path = models.CharField(max_length=500, blank=True, default="")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default="")
    object_repr = models.CharField(max_length=255, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=True, db_index=True)
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_INFO,
        db_index=True,
    )

    class Meta:
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "module"], name="audit_ct_mod_idx"),
            models.Index(fields=["-created_at", "action"], name="audit_ct_act_idx"),
            models.Index(fields=["-created_at", "user"], name="audit_ct_user_idx"),
        ]

    def __str__(self):
        actor = self.username_snapshot or (self.user.username if self.user_id else "anonimo")
        return f"[{self.created_at:%d/%m/%Y %H:%M}] {actor} - {self.module}:{self.action}"
