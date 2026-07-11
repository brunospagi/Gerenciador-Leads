import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_WEBHOOK_FALLBACK_ENV = {
    'DISTRIBUICAO_LEADS': 'N8N_WEBHOOK_URL',
    'CONTROLE_PONTO': 'WEBHOOK_PONTO_URL',
    'WHATSAPP_VENDA_REJEITADA': 'N8N_WHATSAPP_WEBHOOK_URL',
}


def obter_webhook_url(servico):
    """servico = slug de WebhookIntegracao. Prioridade: painel (ativo+url) > env var > None."""
    from .models import WebhookIntegracao

    integracao = WebhookIntegracao.objects.filter(slug=servico).first()
    if integracao is not None:
        if not integracao.ativo:
            return None
        if integracao.url:
            return integracao.url

    env_var = _WEBHOOK_FALLBACK_ENV.get(servico)
    if not env_var:
        return None
    return getattr(settings, env_var, '') or None


def enviar_webhook(servico, payload, timeout=3):
    """POST fire-and-forget: nunca lança exceção pro chamador."""
    import requests

    url = obter_webhook_url(servico)
    if not url:
        return
    try:
        requests.post(url, json=payload, timeout=timeout)
    except Exception as e:
        logger.warning("Falha no webhook '%s': %s", servico, e)


def obter_integracao(campo):
    """campo = nome do atributo em ConfiguracaoIntegracoes (ex: 'evo_crm_api_token').
    Prioridade: valor no painel (se preenchido) > settings.<CAMPO_MAIUSCULO> (env var)."""
    from .models import ConfiguracaoIntegracoes

    config = ConfiguracaoIntegracoes.get_solo()
    valor_db = getattr(config, campo, '') or ''
    if valor_db:
        return valor_db
    return getattr(settings, campo.upper(), '')


def has_module_action(user, module_slug, action):
    """action em {'visualizar', 'criar', 'editar', 'excluir'}."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, 'profile', None)
    if getattr(profile, 'nivel_acesso', '') == 'ADMIN':
        return True

    from .models import PermissaoModulo

    perm = PermissaoModulo.objects.filter(user=user, modulo__slug=module_slug).first()
    if perm is None:
        return False
    return getattr(perm, f'pode_{action}', False)


ACOES = ('visualizar', 'criar', 'editar', 'excluir')


def obter_matriz_permissoes(user):
    """Matriz {modulo_slug: {'visualizar':bool,'criar':bool,'editar':bool,'excluir':bool}}
    pra todos os modulos, em no maximo 2 queries (evita N+1 nos templates/nav)."""
    from .models import ModuloSistema, PermissaoModulo

    modulos = list(ModuloSistema.objects.all())

    if not getattr(user, 'is_authenticated', False):
        return {m.slug: {acao: False for acao in ACOES} for m in modulos}

    acesso_total = user.is_superuser
    if not acesso_total:
        profile = getattr(user, 'profile', None)
        acesso_total = getattr(profile, 'nivel_acesso', '') == 'ADMIN'

    if acesso_total:
        return {m.slug: {acao: True for acao in ACOES} for m in modulos}

    permissoes = {p.modulo_id: p for p in PermissaoModulo.objects.filter(user=user)}
    resultado = {}
    for modulo in modulos:
        perm = permissoes.get(modulo.id)
        resultado[modulo.slug] = {
            acao: bool(perm and getattr(perm, f'pode_{acao}'))
            for acao in ACOES
        }
    return resultado
