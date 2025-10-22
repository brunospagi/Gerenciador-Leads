from django.db import models
from django.core.exceptions import ValidationError

# Singleton pattern for the TV Video settings
class TVVideo(models.Model):
    video_url = models.URLField(
        verbose_name="URL do Vídeo (Recomendado YouTube Embed ou MP4 direto)",
        help_text="O link do vídeo para exibição na TV. Para YouTube, use o link de embed (ex: https://www.youtube.com/embed/SEU_ID?autoplay=1&mute=1&loop=1&playlist=SEU_ID).",
        default='https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&mute=1&loop=1&playlist=dQw4w9WgXcQ'
    )
    titulo = models.CharField(
        max_length=100,
        verbose_name="Título do Vídeo",
        default="Vídeo Promocional"
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Atualização"
    )

    class Meta:
        verbose_name = "Configuração de Vídeo da TV"
        verbose_name_plural = "Configuração de Vídeo da TV"

    # Enforce Singleton Pattern
    def clean(self):
        if not self.pk and TVVideo.objects.exists():
            raise ValidationError('Só pode haver uma configuração de vídeo para a TV. Por favor, edite a existente.')

    def save(self, *args, **kwargs):
        # A data de atualização (last_updated) é automaticamente salva
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_video(cls):
        # Retorna a única instância existente ou cria uma se não houver
        return cls.objects.first()

    def __str__(self):
        return self.titulo