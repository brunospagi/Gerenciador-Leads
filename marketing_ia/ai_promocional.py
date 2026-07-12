import base64
import json
import logging
import re
import time

import requests
from django.conf import settings

from avaliacoes.ai_runtime import get_gemini_runtime
from configuracoes.models import PROMPT_IMAGEM_PADRAO, PROMPT_IMAGEM_LEONARDO_PADRAO
from configuracoes.resolver import obter_integracao

from . import image_overlay
from . import leonardo_client
from . import openai_client

logger = logging.getLogger(__name__)

IMAGE_MODEL = getattr(settings, 'GEMINI_IMAGE_MODEL', 'gemini-2.5-flash-image')

SYSTEM_INSTRUCTION_LEGENDA = (
    "Você é o social media da SPAGI Motors, uma revenda de carros e motos seminovos. "
    "Escreva uma legenda curta, chamativa e profissional para Instagram/Facebook "
    "anunciando o veículo abaixo. Use no máximo 5 linhas, emojis com moderação, "
    "destaque o principal diferencial, inclua o preço formatado em Reais e termine "
    "com uma chamada para ação (WhatsApp/DM). Depois da legenda, na última linha, "
    "liste de 5 a 8 hashtags relevantes separadas por espaço, prefixadas com '#'. "
    "Retorne apenas JSON válido com as chaves 'legenda' e 'hashtags' (string única)."
)

SYSTEM_INSTRUCTION_CHAMADA = (
    "Você é o social media da SPAGI Motors, uma revenda de carros e motos seminovos. "
    "A partir dos dados do veículo abaixo, escreva só UMA frase bem curta e chamativa "
    "(no máximo 5 palavras) para estampar em cima da foto do anúncio, tipo "
    "'OPORTUNIDADE ÚNICA', 'SAIU MAIS BARATO' ou 'SUPER OFERTA'. Sem emoji, sem "
    "pontuação no final, sem aspas. Responda só com a frase, nada mais."
)

CHAMADA_FALLBACK = "OPORTUNIDADE IMPERDÍVEL"


def _dados_veiculo_para_prompt(anuncio):
    partes = [
        f"Título: {anuncio.titulo}",
        f"Marca: {anuncio.marca or '-'}",
        f"Modelo: {anuncio.modelo or '-'}",
        f"Ano: {anuncio.ano or '-'}",
        f"KM: {anuncio.km or '-'}",
        f"Cor: {anuncio.cor or '-'}",
        f"Preço: R$ {anuncio.preco:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
        if anuncio.preco else "Preço: consulte",
    ]
    if anuncio.condicoes:
        partes.append(f"Condições: {', '.join(anuncio.condicoes)}")
    return "\n".join(partes)


def baixar_foto(url, timeout=20):
    """Baixa uma foto do anúncio (hospedada no CDN do site) e retorna (bytes, mime_type)."""
    resposta = requests.get(url, timeout=timeout)
    resposta.raise_for_status()
    mime_type = resposta.headers.get('Content-Type', 'image/jpeg').split(';')[0]
    return resposta.content, mime_type


def gerar_legenda(anuncio):
    """Retorna (legenda, hashtags, modelo_usado) ou (None, None, None) se a IA falhar."""
    client, model_name, erro = get_gemini_runtime()
    if erro or not client:
        logger.warning('Gemini indisponível para gerar legenda: %s', erro)
        return None, None, None

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[{"text": _dados_veiculo_para_prompt(anuncio)}],
            config={
                "system_instruction": SYSTEM_INSTRUCTION_LEGENDA,
                "response_mime_type": "application/json",
            },
        )
        cleaned = re.sub(r'```json\s*|\s*```', '', response.text or '', flags=re.DOTALL).strip()
        data = json.loads(cleaned)
        return data.get('legenda'), data.get('hashtags'), model_name
    except Exception as exc:
        logger.warning('Erro ao gerar legenda com Gemini: %s', exc)
        return None, None, None


def gerar_chamada_ia(anuncio):
    """
    Gera só a frase curta de destaque (ex: "OPORTUNIDADE ÚNICA") pro banner da
    imagem sem IA de geração (provedor OVERLAY) — usa o Gemini só pra texto,
    nenhum custo de geração de imagem. Sempre retorna uma frase (cai pro
    fallback fixo se a IA estiver indisponível ou falhar).
    """
    client, model_name, erro = get_gemini_runtime()
    if erro or not client:
        logger.warning('Gemini indisponível para gerar chamada: %s', erro)
        return CHAMADA_FALLBACK

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[{"text": _dados_veiculo_para_prompt(anuncio)}],
            config={"system_instruction": SYSTEM_INSTRUCTION_CHAMADA},
        )
        texto = (response.text or '').strip().strip('"').strip("'")
        return texto or CHAMADA_FALLBACK
    except Exception as exc:
        logger.warning('Erro ao gerar chamada com Gemini: %s', exc)
        return CHAMADA_FALLBACK


def gerar_imagem_promocional(anuncio, foto_bytes, mime_type, max_tentativas=3, template_overlay=None, resolucao_overlay=None):
    """
    Gera a imagem promocional usando o provedor configurado em
    Configurações > Integrações Externas (padrão: Gemini). Retorna
    (imagem_bytes, mime_type_saida, modelo_usado, prompt_usado) ou
    (None, None, None, None) se a IA estiver indisponível ou falhar — o
    caller deve tratar isso como uma falha esperada, não uma exceção.

    template_overlay/resolucao_overlay: só valem pro provedor OVERLAY — permitem
    a tela de prévia sobrepor o template/resolução padrão configurados, sem
    precisar alterar a configuração global.
    """
    from configuracoes.models import ConfiguracaoIntegracoes

    provedor = ConfiguracaoIntegracoes.get_solo().provedor_imagem_ia
    if provedor == 'LEONARDO':
        return _gerar_imagem_leonardo(anuncio, foto_bytes, mime_type)
    if provedor == 'OPENAI':
        return _gerar_imagem_openai(anuncio, foto_bytes, mime_type)
    if provedor == 'OVERLAY':
        return _gerar_imagem_overlay(anuncio, foto_bytes, mime_type, template_overlay, resolucao_overlay)
    return _gerar_imagem_gemini(anuncio, foto_bytes, mime_type, max_tentativas=max_tentativas)


def _gerar_imagem_overlay(anuncio, foto_bytes, mime_type, template_overlay=None, resolucao_overlay=None):
    """Provedor 'sem IA de imagem': usa a foto real como está, só desenha o
    texto por cima (Pillow). O Gemini entra só pra gerar a frase de destaque —
    se ele falhar, cai pro fallback fixo em vez de travar a geração inteira."""
    chamada = gerar_chamada_ia(anuncio)
    template = template_overlay or obter_integracao('template_imagem_overlay') or image_overlay.TEMPLATE_PADRAO
    resolucao = resolucao_overlay or obter_integracao('resolucao_imagem_overlay') or image_overlay.RESOLUCAO_PADRAO
    try:
        imagem_bytes, mime_saida = image_overlay.montar_imagem_overlay(
            foto_bytes, anuncio, chamada, template=template, resolucao=resolucao,
        )
        return imagem_bytes, mime_saida, f'overlay:pillow:{template}:{resolucao}', chamada
    except image_overlay.ImageOverlayError as exc:
        logger.warning('Erro ao montar imagem com overlay: %s', exc)
        return None, None, None, None
    except Exception as exc:
        logger.warning('Erro inesperado ao montar imagem com overlay: %s', exc)
        return None, None, None, None


def _gerar_imagem_leonardo(anuncio, foto_bytes, mime_type):
    api_key = obter_integracao('leonardo_api_key')
    if not api_key:
        logger.warning('Leonardo.Ai indisponível: chave da API não configurada (Admin/.env).')
        return None, None, None, None

    model_id = obter_integracao('leonardo_model_id') or leonardo_client.MODEL_ID_PADRAO
    prompt = obter_integracao('prompt_imagem_leonardo') or PROMPT_IMAGEM_LEONARDO_PADRAO
    try:
        imagem_bytes, mime_saida = leonardo_client.gerar_imagem_leonardo(
            prompt, foto_bytes, mime_type, api_key, model_id=model_id,
        )
        return imagem_bytes, mime_saida, f'leonardo:{model_id}', prompt
    except leonardo_client.LeonardoError as exc:
        logger.warning('Erro ao gerar imagem promocional com Leonardo.Ai: %s', exc)
        return None, None, None, None
    except Exception as exc:
        logger.warning('Erro inesperado ao chamar o Leonardo.Ai: %s', exc)
        return None, None, None, None


def _gerar_imagem_openai(anuncio, foto_bytes, mime_type):
    api_key = obter_integracao('openai_api_key')
    if not api_key:
        logger.warning('OpenAI indisponível: chave da API não configurada (Admin/.env).')
        return None, None, None, None

    model_id = obter_integracao('openai_image_model') or openai_client.MODEL_ID_PADRAO
    quality = obter_integracao('openai_image_quality') or 'medium'
    prompt = obter_integracao('prompt_imagem') or PROMPT_IMAGEM_PADRAO
    try:
        imagem_bytes, mime_saida = openai_client.gerar_imagem_openai(
            prompt, foto_bytes, mime_type, api_key, model_id=model_id, quality=quality,
        )
        return imagem_bytes, mime_saida, f'openai:{model_id}:{quality}', prompt
    except openai_client.OpenAIImageError as exc:
        logger.warning('Erro ao gerar imagem promocional com OpenAI: %s', exc)
        return None, None, None, None
    except Exception as exc:
        logger.warning('Erro inesperado ao chamar a OpenAI: %s', exc)
        return None, None, None, None


def _gerar_imagem_gemini(anuncio, foto_bytes, mime_type, max_tentativas=3):
    client, _, erro = get_gemini_runtime()
    if erro or not client:
        logger.warning('Gemini indisponível para gerar imagem promocional: %s', erro)
        return None, None, None, None

    modelo = obter_integracao('gemini_image_model') or IMAGE_MODEL
    prompt = obter_integracao('prompt_imagem') or PROMPT_IMAGEM_PADRAO
    contents = [
        {"text": prompt},
        {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(foto_bytes).decode('utf-8')}},
    ]

    for tentativa in range(1, max_tentativas + 1):
        try:
            response = client.models.generate_content(model=modelo, contents=contents)
            for candidate in response.candidates or []:
                for part in candidate.content.parts or []:
                    inline_data = getattr(part, 'inline_data', None)
                    if inline_data and inline_data.data:
                        dados = inline_data.data
                        if isinstance(dados, str):
                            dados = base64.b64decode(dados)
                        return dados, inline_data.mime_type or 'image/png', modelo, prompt
            logger.warning('Resposta da Gemini não trouxe imagem para %s', anuncio.titulo)
            return None, None, None, None
        except Exception as exc:
            error_upper = str(exc).upper()
            transitorio = '503' in error_upper or 'UNAVAILABLE' in error_upper or 'HIGH DEMAND' in error_upper
            if transitorio and tentativa < max_tentativas:
                time.sleep(tentativa)
                continue
            logger.warning('Erro ao gerar imagem promocional com Gemini: %s', exc)
            return None, None, None, None

    return None, None, None, None
