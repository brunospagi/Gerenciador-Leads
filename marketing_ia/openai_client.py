"""
Cliente mínimo para a API de imagens da OpenAI, usado como provedor alternativo
de geração de imagem no marketing_ia (as outras opções são Gemini, em
ai_promocional.py, e Leonardo.Ai, em leonardo_client.py).

Ao contrário do Leonardo (upload em duas etapas + job assíncrono com polling),
o endpoint /v1/images/edits da OpenAI é síncrono: manda a foto de referência e o
prompt na mesma requisição multipart/form-data e a imagem já volta pronta
(base64) na resposta.

Referência: https://platform.openai.com/docs/api-reference/images/createEdit
"""
import base64
import mimetypes

import requests
from django.conf import settings

BASE_URL = 'https://api.openai.com/v1'

# gpt-image-1-mini é o modelo de imagem mais barato da OpenAI atualmente
# (bem mais barato que gpt-image-1/dall-e-3) e suporta o endpoint /images/edits
# com foto de referência, que é o que precisamos aqui. Configurável via
# OPENAI_IMAGE_MODEL no .env caso queira usar outro (ex: gpt-image-1).
MODEL_ID_PADRAO = getattr(settings, 'OPENAI_IMAGE_MODEL', None) or 'gpt-image-1-mini'

TIMEOUT_REQUEST = 90


class OpenAIImageError(Exception):
    """Erro esperado em qualquer etapa do fluxo de geração de imagem da OpenAI."""


def _extrair_mensagem_erro(resp):
    try:
        return resp.json().get('error', {}).get('message') or resp.text[:500]
    except ValueError:
        return resp.text[:500]


def gerar_imagem_openai(prompt, foto_bytes, mime_type, api_key, model_id=None, quality=None):
    """
    Gera a imagem promocional usando a foto real do veículo como referência,
    via /images/edits. Retorna (bytes, mime_type) ou levanta OpenAIImageError
    com uma mensagem amigável — o caller (ai_promocional.py) decide como
    logar/propagar.
    """
    extensao = (mimetypes.guess_extension(mime_type) or '.jpg').lstrip('.')
    if extensao == 'jpe':
        extensao = 'jpg'

    resp = requests.post(
        f'{BASE_URL}/images/edits',
        headers={'authorization': f'Bearer {api_key}'},
        data={
            'model': model_id or MODEL_ID_PADRAO,
            'prompt': prompt,
            'n': '1',
            'size': '1024x1024',
            'quality': quality or 'medium',
            'output_format': 'jpeg',
        },
        files={'image': (f'referencia.{extensao}', foto_bytes, mime_type)},
        timeout=TIMEOUT_REQUEST,
    )
    if not resp.ok:
        raise OpenAIImageError(f'Falha ao gerar imagem (/images/edits): HTTP {resp.status_code} — {_extrair_mensagem_erro(resp)}')

    dados = resp.json()
    itens = dados.get('data') or []
    if not itens or not itens[0].get('b64_json'):
        raise OpenAIImageError(f'Resposta inesperada de /images/edits: {resp.text[:500]}')

    imagem_bytes = base64.b64decode(itens[0]['b64_json'])
    formato_saida = dados.get('output_format') or 'jpeg'
    mime_saida = f'image/{formato_saida}'
    return imagem_bytes, mime_saida
