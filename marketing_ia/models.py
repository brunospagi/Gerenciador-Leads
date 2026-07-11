import os
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

from crmspagi.storage_backends import PublicMediaStorage

User = get_user_model()


def get_post_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1] or '.jpg'
    unique_filename = f"{uuid.uuid4()}{ext}"
    return f"marketing_ia/posts/{instance.anuncio.external_id}/{unique_filename}"


class VeiculoAnuncio(models.Model):
    """Anúncio de veículo raspado do estoque público (spagimotors.com.br)."""

    TIPO_CHOICES = [
        ('CARRO', 'Carro'),
        ('MOTO', 'Moto'),
        ('OUTRO', 'Outro'),
    ]

    external_id = models.CharField(max_length=30, unique=True, verbose_name='ID no site')
    url = models.URLField(max_length=500, verbose_name='URL do anúncio')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='OUTRO')

    marca = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    titulo = models.CharField(max_length=255, verbose_name='Título completo do anúncio')
    preco = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    ano = models.CharField(max_length=15, blank=True, null=True)
    km = models.CharField(max_length=20, blank=True, null=True)
    cor = models.CharField(max_length=50, blank=True, null=True)
    cambio = models.CharField(max_length=50, blank=True, null=True)
    combustivel = models.CharField(max_length=50, blank=True, null=True)
    carroceria = models.CharField(max_length=50, blank=True, null=True)
    portas = models.CharField(max_length=30, blank=True, null=True)

    condicoes = models.JSONField(default=list, blank=True, verbose_name='Ex: Aceita Troca, IPVA Pago')
    opcionais = models.JSONField(default=list, blank=True)
    descricao = models.TextField(blank=True, null=True)

    foto_principal_url = models.URLField(max_length=500, blank=True, null=True)
    fotos_urls = models.JSONField(default=list, blank=True, verbose_name='URLs das fotos em alta resolução')

    ativo = models.BooleanField(default=True, verbose_name='Ainda encontrado no estoque do site')
    coletado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Anúncio de Veículo (raspado)'
        verbose_name_plural = 'Anúncios de Veículos (raspados)'
        ordering = ['-atualizado_em']

    def __str__(self):
        return self.titulo or self.external_id


class LoteGeracao(models.Model):
    """Agrupa os posts criados por um disparo de 'gerar para todos' pela tela do CRM."""

    STATUS_CHOICES = [
        ('RODANDO', 'Rodando'),
        ('CONCLUIDO', 'Concluído'),
        ('ERRO', 'Erro'),
    ]

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='RODANDO')
    iniciado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    alvo_ids = models.JSONField(default=list, blank=True, verbose_name='IDs dos VeiculoAnuncio incluídos no lote')
    total_alvo = models.PositiveIntegerField(default=0)
    total_gerado = models.PositiveIntegerField(default=0)
    total_falhas = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    concluido_em = models.DateTimeField(null=True, blank=True)
    erro = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Lote de Geração'
        verbose_name_plural = 'Lotes de Geração'
        ordering = ['-criado_em']

    def __str__(self):
        return f'Lote #{self.pk} ({self.get_status_display()})'


class PostPromocional(models.Model):
    """Post gerado com IA (foto + legenda) a partir de um VeiculoAnuncio."""

    STATUS_CHOICES = [
        ('RASCUNHO', 'Rascunho'),
        ('APROVADO', 'Aprovado'),
        ('PUBLICADO', 'Publicado'),
        ('DESCARTADO', 'Descartado'),
    ]

    anuncio = models.ForeignKey(VeiculoAnuncio, on_delete=models.CASCADE, related_name='posts')
    lote = models.ForeignKey(LoteGeracao, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    imagem = models.ImageField(
        upload_to=get_post_upload_path,
        storage=PublicMediaStorage(),
        verbose_name='Imagem promocional gerada',
    )
    legenda = models.TextField(verbose_name='Legenda para redes sociais')
    hashtags = models.CharField(max_length=500, blank=True, null=True)

    prompt_imagem = models.TextField(blank=True, null=True, editable=False)
    modelo_ia_imagem = models.CharField(max_length=100, blank=True, null=True, editable=False)
    modelo_ia_texto = models.CharField(max_length=100, blank=True, null=True, editable=False)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='RASCUNHO')
    gerado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    gerado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Post Promocional (IA)'
        verbose_name_plural = 'Posts Promocionais (IA)'
        ordering = ['-gerado_em']

    def __str__(self):
        return f"Post {self.anuncio.titulo} ({self.get_status_display()})"


class SincronizacaoEstoque(models.Model):
    """Registro (singleton) do status da última raspagem disparada pela tela do CRM."""

    STATUS_CHOICES = [
        ('OCIOSO', 'Ocioso'),
        ('RODANDO', 'Rodando'),
        ('CONCLUIDO', 'Concluído'),
        ('ERRO', 'Erro'),
    ]

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OCIOSO')
    iniciado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    iniciado_em = models.DateTimeField(null=True, blank=True)
    concluido_em = models.DateTimeField(null=True, blank=True)
    resultado = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Sincronização de Estoque'
        verbose_name_plural = 'Sincronizações de Estoque'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class EnvioWebhook(models.Model):
    """
    Registro de cada tentativa de envio de um post para um webhook.
    Reaproveita o cadastro de webhooks de configuracoes.WebhookIntegracao
    (mesma tela usada pelos demais eventos do sistema) em vez de manter uma
    lista de destinos própria.
    """

    post = models.ForeignKey(PostPromocional, on_delete=models.CASCADE, related_name='envios')
    webhook = models.ForeignKey('configuracoes.WebhookIntegracao', on_delete=models.SET_NULL, null=True)
    enviado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    sucesso = models.BooleanField(default=False)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    erro = models.CharField(max_length=255, blank=True, null=True)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Envio de Webhook'
        verbose_name_plural = 'Envios de Webhook'
        ordering = ['-enviado_em']

    def __str__(self):
        return f'Envio #{self.pk} — {self.webhook} ({"ok" if self.sucesso else "falha"})'
