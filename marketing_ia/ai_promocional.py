import base64
import json
import logging
import re
import time

import requests
from django.conf import settings

from avaliacoes.ai_runtime import get_gemini_runtime

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

PROMPT_IMAGEM = (
    "Use a foto enviada como referência do veículo real (mantenha a carroceria, cor e "
    "detalhes fiéis ao original, sem alterar o veículo). Recrie a cena colocando o "
    "veículo em um showroom moderno e bem iluminado (ou pátio externo elegante ao "
    "entardecer), com reflexo sutil no chão, aparência profissional de anúncio "
    "publicitário para redes sociais, formato quadrado (1:1), alta qualidade "
    "fotorrealista. Não inclua nenhum texto, logotipo ou marca d'água na imagem."
)


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


def gerar_imagem_promocional(anuncio, foto_bytes, mime_type, max_tentativas=3):
    """
    Envia a foto real do veículo + prompt para o modelo de imagem do Gemini e
    retorna (imagem_bytes, mime_type_saida, modelo_usado) ou (None, None, None).
    """
    client, _, erro = get_gemini_runtime()
    if erro or not client:
        logger.warning('Gemini indisponível para gerar imagem promocional: %s', erro)
        return None, None, None

    contents = [
        {"text": PROMPT_IMAGEM},
        {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(foto_bytes).decode('utf-8')}},
    ]

    for tentativa in range(1, max_tentativas + 1):
        try:
            response = client.models.generate_content(model=IMAGE_MODEL, contents=contents)
            for candidate in response.candidates or []:
                for part in candidate.content.parts or []:
                    inline_data = getattr(part, 'inline_data', None)
                    if inline_data and inline_data.data:
                        dados = inline_data.data
                        if isinstance(dados, str):
                            dados = base64.b64decode(dados)
                        return dados, inline_data.mime_type or 'image/png', IMAGE_MODEL
            logger.warning('Resposta da Gemini não trouxe imagem para %s', anuncio.titulo)
            return None, None, None
        except Exception as exc:
            error_upper = str(exc).upper()
            transitorio = '503' in error_upper or 'UNAVAILABLE' in error_upper or 'HIGH DEMAND' in error_upper
            if transitorio and tentativa < max_tentativas:
                time.sleep(tentativa)
                continue
            logger.warning('Erro ao gerar imagem promocional com Gemini: %s', exc)
            return None, None, None

    return None, None, None
