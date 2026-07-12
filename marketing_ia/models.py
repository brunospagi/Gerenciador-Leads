import os
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

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
    motorizacao = models.CharField(
        max_length=30, blank=True, null=True, verbose_name='Motorização',
        help_text='Ex: 1.0, 1.6 Turbo — raspado do bloco técnico do anúncio, quando disponível.',
    )

    condicoes = models.JSONField(default=list, blank=True, verbose_name='Ex: Aceita Troca, IPVA Pago')
    # Sinalizadores próprios pra "Aceita troca"/"IPVA pago": derivados automaticamente
    # das condições raspadas do site a cada sincronização, mas editáveis manualmente
    # (checkbox no admin/detalhe) pra corrigir texto inconsistente do site sem
    # depender só do que a IA entende do texto cru de `condicoes`.
    ipva_pago = models.BooleanField(default=False, verbose_name='IPVA pago')
    aceita_troca = models.BooleanField(default=False, verbose_name='Aceita troca')
    # Mesma lógica: derivado automaticamente dos `opcionais` raspados (presença de
    # ar condicionado + direção hidráulica/elétrica + vidro elétrico), editável no
    # admin. Vira uma vantagem pronta pra IA usar (ex: "Veículo completo").
    veiculo_completo = models.BooleanField(default=False, verbose_name='Veículo completo')
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


class LayoutOverlay(models.Model):
    """
    Layout do overlay Pillow (provedor "sem IA de imagem") criado/editado
    visualmente no editor drag-and-drop, em vez de um dos 3 templates fixos em
    código (FAIXA_INFERIOR/SELO_DIAGONAL/CARTAO_CENTRAL).

    `elementos` guarda a lista de camadas, na ordem em que são desenhadas
    (o item seguinte fica por cima do anterior). Cada camada é um dict com
    posição/tamanho em FRAÇÕES de 0 a 1 do canvas (não pixels), pra funcionar
    em qualquer uma das resoluções de RESOLUCOES sem precisar converter nada:
      {"tipo": "forma", "x": 0, "y": 0.7, "largura": 1, "altura": 0.3,
       "cor_fundo": "#0f172a", "opacidade": 0.9, "arredondado": 0}
      {"tipo": "texto", "campo": "chamada"|"titulo"|"preco"|"fixo",
       "texto_fixo": "...", "x": 0.06, "y": 0.72, "largura": 0.6,
       "tamanho_fonte": 0.05, "cor_texto": "#ffffff", "alinhamento": "esquerda",
       "maiusculas": true}
      {"tipo": "logo", "x": 0.8, "y": 0.7, "altura": 0.07}
    """

    nome = models.CharField(max_length=80, verbose_name='Nome do layout')
    elementos = models.JSONField(default=list, blank=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Layout de Overlay (customizado)'
        verbose_name_plural = 'Layouts de Overlay (customizados)'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def chave_template(self):
        """Valor salvo em ConfiguracaoIntegracoes.template_imagem_overlay (ou
        passado como override na prévia) pra apontar pra este layout em vez de
        um dos 3 templates fixos — o prefixo distingue os dois casos."""
        return f'CUSTOM:{self.pk}'


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


class PreviewPost(models.Model):
    """
    Prévia de um post gerado, aguardando confirmação do usuário antes de virar
    um PostPromocional de verdade. A imagem fica em BinaryField (banco), não em
    ImageField/S3: assim uma prévia descartada nunca cria lixo no MinIO, e o
    conteúdo fica visível a qualquer worker do gunicorn (o cache padrão do
    Django aqui é por processo, não seria confiável entre a requisição que gera
    e a que confirma/descarta).
    """

    anuncio = models.ForeignKey(VeiculoAnuncio, on_delete=models.CASCADE, related_name='previews')
    imagem_bytes = models.BinaryField()
    imagem_mime_type = models.CharField(max_length=30, default='image/jpeg')
    legenda = models.TextField(blank=True, null=True)
    hashtags = models.CharField(max_length=500, blank=True, null=True)
    prompt_imagem = models.TextField(blank=True, null=True)
    modelo_ia_imagem = models.CharField(max_length=100, blank=True, null=True)
    modelo_ia_texto = models.CharField(max_length=100, blank=True, null=True)
    gerado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Prévia de Post (IA)'
        verbose_name_plural = 'Prévias de Post (IA)'
        ordering = ['-criado_em']

    def __str__(self):
        return f"Prévia {self.anuncio.titulo} (#{self.pk})"


class SincronizacaoEstoque(models.Model):
    """Registro (singleton) do status da última raspagem disparada pela tela do CRM."""

    STATUS_CHOICES = [
        ('OCIOSO', 'Ocioso'),
        ('RODANDO', 'Rodando'),
        ('CONCLUIDO', 'Concluído'),
        ('ERRO', 'Erro'),
    ]

    # Se a sincronização ficar "RODANDO" por mais tempo que isso, load() considera
    # que travou (ex: o servidor de desenvolvimento reiniciou no meio da raspagem,
    # matando a thread em segundo plano sem chance de atualizar o status) e destrava
    # sozinha — sem isso, o botão "Atualizar estoque" ficava bloqueado pra sempre.
    TIMEOUT_MINUTOS = 30

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
        if obj.status == 'RODANDO' and obj.iniciado_em:
            if timezone.now() - obj.iniciado_em > timedelta(minutes=cls.TIMEOUT_MINUTOS):
                obj.status = 'ERRO'
                obj.concluido_em = timezone.now()
                obj.resultado = (
                    f'Sincronização interrompida (mais de {cls.TIMEOUT_MINUTOS} min sem concluir — '
                    'provavelmente o servidor reiniciou no meio da raspagem). Tente novamente.'
                )
                obj.save(update_fields=['status', 'concluido_em', 'resultado'])
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
