from django.db import models
from django.core.exceptions import ValidationError
from crmspagi.storage_backends import PublicMediaStorage # Importa o storage customizado

# Singleton pattern for the TV Video settings
class TVVideo(models.Model):
    video_url = models.URLField(
        verbose_name="URL do Vídeo (Recomendado YouTube Embed ou MP4 direto)",
        help_text="O link do vídeo para exibição na TV. Para YouTube, use o link de embed (ex: https://www.youtube.com/embed/SEU_ID?autoplay=1&mute=1&loop=1&playlist=SEU_ID).",
        default='https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&mute=1&loop=1&playlist=dQw4w9WgXcQ'
    )
    
    video_mp4 = models.FileField(
        upload_to='tv_videos/',
        storage=PublicMediaStorage(),
        verbose_name="Upload de Vídeo MP4 (Alternativo)",
        help_text="Use este campo para carregar um arquivo MP4. Se preenchido, terá prioridade sobre a URL do YouTube.",
        blank=True,
        null=True
    )
    
    titulo = models.CharField(
        max_length=100,
        verbose_name="Título do Vídeo",
        default="Vídeo Promocional"
    )
    manual_news_ticker = models.TextField(
        verbose_name="Ticker de Notícias Manual (Opcional)",
        help_text="Texto que será exibido no rodapé da TV, substituindo as notícias da API. Separe as notícias com ' | ' (barra vertical).",
        blank=True,
        null=True
    )
    newsdata_api_key = models.CharField(
        max_length=50,
        verbose_name="Chave API NewsData.io",
        help_text="Chave de acesso para buscar notícias externas (Ex: pub_...)",
        default='pub_9a838f4c10ea441382a5a65d67601949',
        blank=True,
        null=True
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

class Banner(models.Model):
    titulo = models.CharField(max_length=100, verbose_name="Título da Novidade")
    imagem = models.ImageField(upload_to='banners/', verbose_name="Imagem do Banner (1200x400 recom.)")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição Curta")
    link = models.URLField(blank=True, null=True, verbose_name="Link de Destino (Opcional)")
    
    ativo = models.BooleanField(default=True, verbose_name="Exibir no Portal?")
    ordem = models.IntegerField(default=0, help_text="Menor número aparece primeiro")
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Banner de Novidade"
        verbose_name_plural = "Banners do Portal"
        ordering = ['ordem', '-data_criacao']

    def __str__(self):
        return self.titulo