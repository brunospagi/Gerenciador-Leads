from django.conf import settings
from django.db import models
from django.utils import timezone


class WhatsAppInstance(models.Model):
    nome = models.CharField(max_length=100, default='Principal')
    api_base_url = models.URLField()
    api_key = models.CharField(max_length=255)
    instance_name = models.CharField(max_length=120)
    webhook_secret = models.CharField(max_length=255, blank=True, null=True)
    ativo = models.BooleanField(default=True)
    status_conexao = models.CharField(max_length=50, default='desconhecido')
    qr_code_base64 = models.TextField(blank=True)
    ultima_resposta = models.JSONField(default=dict, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Instancia WhatsApp'
        verbose_name_plural = 'Instancias WhatsApp'

    def __str__(self):
        return f'{self.nome} ({self.instance_name})'


class WhatsAppConversation(models.Model):
    instance = models.ForeignKey(
        WhatsAppInstance,
        on_delete=models.SET_NULL,
        related_name='conversas',
        null=True,
        blank=True,
    )
    wa_id = models.CharField(max_length=80, unique=True, db_index=True)
    nome_contato = models.CharField(max_length=180, blank=True)
    avatar_url = models.URLField(blank=True)
    e_grupo = models.BooleanField(default=False)
    ultima_mensagem = models.TextField(blank=True)
    ultima_mensagem_em = models.DateTimeField(default=timezone.now, db_index=True)
    nao_lidas = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-ultima_mensagem_em']
        verbose_name = 'Conversa WhatsApp'
        verbose_name_plural = 'Conversas WhatsApp'

    def __str__(self):
        return self.nome_exibicao

    @property
    def nome_exibicao(self):
        return self.nome_contato or self.wa_id


class WhatsAppMessage(models.Model):
    class Direction(models.TextChoices):
        RECEBIDA = 'IN', 'Recebida'
        ENVIADA = 'OUT', 'Enviada'
        SISTEMA = 'SYSTEM', 'Sistema'

    class Status(models.TextChoices):
        PENDENTE = 'pending', 'Pendente'
        ENVIADA = 'sent', 'Enviada'
        ENTREGUE = 'delivered', 'Entregue'
        LIDA = 'read', 'Lida'
        FALHA = 'failed', 'Falha'

    conversa = models.ForeignKey(
        WhatsAppConversation,
        on_delete=models.CASCADE,
        related_name='mensagens',
    )
    external_id = models.CharField(max_length=150, blank=True, null=True, unique=True)
    direcao = models.CharField(max_length=10, choices=Direction.choices)
    conteudo = models.TextField(blank=True)
    media_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_mensagens_enviadas',
    )
    payload = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    recebido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['criado_em']
        verbose_name = 'Mensagem WhatsApp'
        verbose_name_plural = 'Mensagens WhatsApp'

    def __str__(self):
        return f'{self.conversa.nome_exibicao} - {self.get_direcao_display()}'
