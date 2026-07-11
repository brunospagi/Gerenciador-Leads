from django.conf import settings
from django.db import models


class WebhookIntegracao(models.Model):
    """Cadastro extensível de webhooks n8n: os slugs de sistema vêm com seed
    (sistema=True), mas o admin pode criar novas linhas livremente pra outras
    funções — o slug fica disponível pro código chamar enviar_webhook(slug, payload)
    assim que alguém integrar aquele ponto."""

    nome = models.CharField(max_length=100, verbose_name="Nome / Função")
    slug = models.SlugField(
        max_length=50,
        unique=True,
        verbose_name="Identificador (usado no código)",
        help_text="Ex: WHATSAPP_VENDA_REJEITADA. Não altere depois que o evento já estiver integrado.",
    )
    descricao = models.CharField(max_length=255, blank=True, verbose_name="Quando dispara?")
    url = models.URLField(
        max_length=500, blank=True,
        help_text="Em branco usa a variável de ambiente padrão (se houver).",
    )
    ativo = models.BooleanField(default=True, verbose_name="Envio ativo?")
    sistema = models.BooleanField(default=False, editable=False, verbose_name="Evento nativo do sistema")
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "Webhook de Integração"
        verbose_name_plural = "Webhooks de Integração"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class ServicoWebhook:
    """Slugs dos eventos já integrados no código (seed via migration, sistema=True)."""
    DISTRIBUICAO_LEADS = 'DISTRIBUICAO_LEADS'
    CONTROLE_PONTO = 'CONTROLE_PONTO'
    WHATSAPP_VENDA_REJEITADA = 'WHATSAPP_VENDA_REJEITADA'


class ConfiguracaoIntegracoes(models.Model):
    """Singleton (get_solo) para credenciais externas hoje só disponíveis via env var."""

    evolution_api_url = models.CharField(max_length=255, blank=True, verbose_name="Evolution API - URL")
    evolution_api_key = models.CharField(max_length=255, blank=True, verbose_name="Evolution API - Chave")
    evolution_instance = models.CharField(max_length=100, blank=True, verbose_name="Evolution API - Instância")

    evo_crm_api_url = models.CharField(max_length=255, blank=True, verbose_name="EVO CRM - URL da API")
    evo_crm_api_token = models.CharField(max_length=255, blank=True, verbose_name="EVO CRM - Token")
    evo_crm_pipeline_id = models.CharField(max_length=100, blank=True, verbose_name="EVO CRM - Pipeline ID")
    evo_crm_pipeline_stage_id = models.CharField(max_length=100, blank=True, verbose_name="EVO CRM - Stage ID")

    PROVEDOR_IMAGEM_CHOICES = [
        ('GEMINI', 'Gemini (Google)'),
        ('LEONARDO', 'Leonardo.Ai'),
    ]
    provedor_imagem_ia = models.CharField(
        max_length=20, choices=PROVEDOR_IMAGEM_CHOICES, default='GEMINI',
        verbose_name="Provedor de geração de imagem (Marketing IA)",
    )
    leonardo_api_key = models.CharField(max_length=255, blank=True, verbose_name="Leonardo.Ai - Chave da API")

    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "Configuração de Integrações Externas"
        verbose_name_plural = "Configurações de Integrações Externas"

    def __str__(self):
        return "Integrações Externas"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ModuloSistema(models.Model):
    """Catálogo dinâmico de módulos do sistema (substitui o MODULE_FIELD_MAP fixo)."""

    slug = models.SlugField(max_length=40, unique=True)
    nome = models.CharField(max_length=100)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Módulo do Sistema"
        verbose_name_plural = "Módulos do Sistema"
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class PermissaoModulo(models.Model):
    """Matriz usuário × módulo × ação (Visualizar/Criar/Editar/Excluir)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='permissoes_modulo',
    )
    modulo = models.ForeignKey(ModuloSistema, on_delete=models.CASCADE, related_name='permissoes')
    pode_visualizar = models.BooleanField(default=False, verbose_name="Visualizar")
    pode_criar = models.BooleanField(default=False, verbose_name="Criar")
    pode_editar = models.BooleanField(default=False, verbose_name="Editar")
    pode_excluir = models.BooleanField(default=False, verbose_name="Excluir")

    class Meta:
        verbose_name = "Permissão de Módulo"
        verbose_name_plural = "Permissões de Módulo"
        unique_together = ('user', 'modulo')

    def __str__(self):
        return f"{self.user.username} - {self.modulo.slug}"
