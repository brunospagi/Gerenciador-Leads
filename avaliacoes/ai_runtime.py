from django.conf import settings

from .models import ConfiguracaoIA


def get_gemini_runtime():
    """
    Resolve chave/modelo com prioridade para Admin (ConfiguracaoIA),
    com fallback para settings (.env).
    Retorna (client, model_name, error_message_or_none).
    """
    cfg = ConfiguracaoIA.load()
    if not cfg.ativo:
        return None, None, 'Integração de IA está desativada no Admin.'

    model_name = (cfg.modelo or '').strip() or 'gemini-2.5-flash'
    api_key = (cfg.api_key or '').strip() or (getattr(settings, 'GEMINI_API_KEY', None) or '')

    if not api_key:
        return None, model_name, 'API Key do Gemini não configurada (Admin/.env).'

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        return client, model_name, None
    except Exception as exc:
        return None, model_name, f'Falha ao inicializar cliente Gemini: {type(exc).__name__}'
