from django.db import models
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