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


PROMPT_IMAGEM_PADRAO = (
    "Use a foto enviada como referência do veículo real (mantenha a carroceria, cor e "
    "detalhes fiéis ao original, sem alterar o veículo). Recrie a cena colocando o "
    "veículo em um showroom moderno e bem iluminado (ou pátio externo elegante ao "
    "entardecer), com reflexo sutil no chão, aparência profissional de anúncio "
    "publicitário para redes sociais, formato quadrado (1:1), alta qualidade "
    "fotorrealista. Não inclua nenhum texto, logotipo ou marca d'água na imagem."
)

# O Leonardo.Ai não aceita a foto embutida na mesma chamada (ela vai como
# init_image_id, separado) — por isso o prompt aqui é só a descrição textual da
# cena desejada, sem "use a foto enviada como referência".
PROMPT_IMAGEM_LEONARDO_PADRAO = (
    "Professional automotive advertisement photo, the vehicle placed in a modern, "
    "well-lit showroom (or an elegant outdoor lot at dusk), subtle floor reflection, "
    "photorealistic, high quality, social media ad style, square composition. "
    "No text, no logo, no watermark."
)


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
        ('OPENAI', 'OpenAI (GPT Image)'),
        ('OVERLAY', 'Sem IA de imagem (texto sobre a foto real)'),
    ]
    provedor_imagem_ia = models.CharField(
        max_length=20, choices=PROVEDOR_IMAGEM_CHOICES, default='GEMINI',
        verbose_name="Provedor de geração de imagem (Marketing IA)",
    )

    # Prompt da cena para Gemini/OpenAI: os dois recebem a foto do veículo na mesma
    # chamada (inline_data/multipart), por isso o texto assume "use a foto enviada...".
    prompt_imagem = models.TextField(
        default=PROMPT_IMAGEM_PADRAO, blank=True,
        verbose_name="Prompt da cena (Gemini / OpenAI)",
        help_text="Usado por Gemini e OpenAI, que recebem a foto do veículo junto com o prompt.",
    )
    # Prompt do Leonardo.Ai: só texto (a foto vai separada, como init_image_id), por
    # isso não deve mencionar "a foto enviada" - só a descrição da cena desejada.
    prompt_imagem_leonardo = models.TextField(
        default=PROMPT_IMAGEM_LEONARDO_PADRAO, blank=True,
        verbose_name="Prompt da cena (Leonardo.Ai)",
        help_text="Só a descrição da cena (em inglês, se possível) — a foto do veículo vai separada, não mencione 'a foto enviada'.",
    )

    # --- Gemini ---
    # imagen-4.* não aceita foto de referência (só texto->imagem), por isso não entra
    # na lista: aqui só ficam os modelos multimodais (foto + texto -> imagem editada).
    GEMINI_IMAGE_MODEL_CHOICES = [
        ('gemini-2.5-flash-image', 'Gemini 2.5 Flash Image (atual — será descontinuado em out/2026)'),
        ('gemini-3.1-flash-image-preview', 'Gemini 3.1 Flash Image — "Nano Banana 2" (rápido e barato)'),
        ('gemini-3-pro-image-preview', 'Gemini 3 Pro Image — "Nano Banana Pro" (melhor qualidade)'),
    ]
    gemini_image_model = models.CharField(
        max_length=60, choices=GEMINI_IMAGE_MODEL_CHOICES, default='gemini-2.5-flash-image',
        verbose_name="Gemini - Modelo de imagem",
    )

    # --- Leonardo.Ai ---
    # UUIDs oficiais dos modelos do catalogo Leonardo (docs.leonardo.ai/docs/commonly-used-api-values).
    # O default antigo (Leonardo Diffusion XL) e um modelo generico/antigo, nao fotorrealista -
    # por isso a qualidade das imagens de veiculo saia ruim. Lucid Realism e o modelo indicado
    # pela propria Leonardo pra fotografia realista (fotos de produto/comercial).
    LEONARDO_MODEL_CHOICES = [
        ('05ce0082-2d80-4a2d-8653-4d1c85e2418e', 'Lucid Realism (fotorrealista — recomendado)'),
        ('7b592283-e8a7-4c5a-9ba6-d18c31f258b9', 'Lucid Origin'),
        ('de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3', 'Leonardo Phoenix 1.0'),
        ('1e60896f-3c26-4296-8ecc-53e2afecc132', 'Leonardo Diffusion XL (antigo, não recomendado)'),
    ]
    leonardo_api_key = models.CharField(max_length=255, blank=True, verbose_name="Leonardo.Ai - Chave da API")
    leonardo_model_id = models.CharField(
        max_length=60, choices=LEONARDO_MODEL_CHOICES, default='05ce0082-2d80-4a2d-8653-4d1c85e2418e',
        verbose_name="Leonardo.Ai - Modelo",
    )

    # --- OpenAI ---
    # Só os modelos da familia GPT Image, que aceitam foto de referencia via /images/edits
    # (dall-e-2/3 ficaram de fora: dall-e-3 nao tem edicao com referencia, dall-e-2 e bem limitado).
    OPENAI_IMAGE_MODEL_CHOICES = [
        ('gpt-image-1-mini', 'GPT Image 1 Mini (mais barato)'),
        ('gpt-image-1', 'GPT Image 1'),
        ('gpt-image-1.5', 'GPT Image 1.5'),
        ('gpt-image-2', 'GPT Image 2 (melhor qualidade)'),
    ]
    OPENAI_QUALITY_CHOICES = [
        ('low', 'Baixa (mais barata)'),
        ('medium', 'Média'),
        ('high', 'Alta (melhor qualidade, mais cara)'),
    ]
    openai_api_key = models.CharField(max_length=255, blank=True, verbose_name="OpenAI - Chave da API")
    openai_image_model = models.CharField(
        max_length=30, choices=OPENAI_IMAGE_MODEL_CHOICES, default='gpt-image-1-mini',
        verbose_name="OpenAI - Modelo",
    )
    openai_image_quality = models.CharField(
        max_length=10, choices=OPENAI_QUALITY_CHOICES, default='medium',
        verbose_name="OpenAI - Qualidade",
    )

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
