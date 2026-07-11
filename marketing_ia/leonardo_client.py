"""
Cliente mínimo para a API REST do Leonardo.Ai, usado como provedor alternativo
de geração de imagem no marketing_ia (a outra opção é o Gemini, em ai_promocional.py).

Fluxo (baseado nas "recipes" oficiais em docs.leonardo.ai — não há SDK Python
oficial mantido pela Anthropic/Leonardo para este projeto usar):
  1. POST /init-image           -> pede uma URL pré-assinada + id da imagem
  2. POST <url pré-assinada>    -> sobe os bytes da foto original (multipart)
  3. POST /generations          -> cria o job de geração usando a foto como
                                    referência (image guidance / img2img)
  4. GET  /generations/{id}     -> faz polling até status concluído e baixa
                                    a imagem gerada

Como não temos uma API key de teste neste ambiente para validar contra a API
real, o parsing das respostas foi escrito de forma defensiva (tenta os campos
documentados e loga o JSON bruto se não encontrar) — se o formato de resposta
tiver mudado, o log deixa claro o que ajustar.
"""
import logging
import mimetypes
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_URL = 'https://cloud.leonardo.ai/api/rest/v1'

# ID de modelo verificado no exemplo oficial da documentação do Leonardo.Ai
# (docs.leonardo.ai/recipes/generate-with-image-to-image-guidance-using-uploaded-images).
# Não há garantia de que seja o melhor modelo para fotos de veículo — o ideal é o
# admin pegar o ID de um modelo fotorrealista (ex: "Lucid Realism", "Phoenix") em
# app.leonardo.ai e configurar LEONARDO_MODEL_ID no .env, sem precisar mexer no código.
MODEL_ID_PADRAO = getattr(settings, 'LEONARDO_MODEL_ID', None) or '1e60896f-3c26-4296-8ecc-53e2afecc132'

TIMEOUT_REQUEST = 15
TIMEOUT_POLLING_SEGUNDOS = 90
INTERVALO_POLLING_SEGUNDOS = 4


class LeonardoError(Exception):
    """Erro esperado em qualquer etapa do fluxo Leonardo.Ai."""


def _headers(api_key):
    return {
        'accept': 'application/json',
        'content-type': 'application/json',
        'authorization': f'Bearer {api_key}',
    }


def _upload_foto_referencia(api_key, foto_bytes, mime_type):
    extensao = (mimetypes.guess_extension(mime_type) or '.jpg').lstrip('.')
    if extensao == 'jpe':
        extensao = 'jpg'

    resp = requests.post(
        f'{BASE_URL}/init-image',
        json={'extension': extensao},
        headers=_headers(api_key),
        timeout=TIMEOUT_REQUEST,
    )
    resp.raise_for_status()
    dados = resp.json().get('uploadInitImage') or {}
    image_id = dados.get('id')
    upload_url = dados.get('url')
    campos_upload = dados.get('fields') or {}
    if not image_id or not upload_url:
        raise LeonardoError(f'Resposta inesperada de /init-image: {resp.text[:500]}')

    upload_resp = requests.post(
        upload_url,
        data=campos_upload,
        files={'file': (f'referencia.{extensao}', foto_bytes)},
        timeout=TIMEOUT_REQUEST,
    )
    if upload_resp.status_code not in (200, 201, 204):
        raise LeonardoError(f'Falha ao enviar a foto de referência ({upload_resp.status_code}).')

    return image_id


def _criar_generation(api_key, prompt, init_image_id):
    payload = {
        'prompt': prompt,
        'modelId': MODEL_ID_PADRAO,
        'width': 1024,
        'height': 1024,
        'num_images': 1,
        'init_image_id': init_image_id,
        'init_strength': 0.35,  # baixo: preserva o veículo real, só troca o cenário
    }
    resp = requests.post(
        f'{BASE_URL}/generations',
        json=payload,
        headers=_headers(api_key),
        timeout=TIMEOUT_REQUEST,
    )
    resp.raise_for_status()
    dados = resp.json()
    generation_id = (
        dados.get('generationId')
        or (dados.get('sdGenerationJob') or {}).get('generationId')
    )
    if not generation_id:
        raise LeonardoError(f'Resposta inesperada de /generations: {resp.text[:500]}')
    return generation_id


def _extrair_status_e_urls(dados):
    """Procura status e URLs de imagem em qualquer um dos formatos de resposta
    documentados/observados pelo Leonardo (o campo raiz varia: generations_by_pk,
    ou o objeto direto)."""
    raiz = dados.get('generations_by_pk') or dados
    status = (raiz.get('status') or '').upper()
    imagens = raiz.get('generated_images') or raiz.get('images') or []
    urls = [img.get('url') for img in imagens if img.get('url')]
    return status, urls


def _aguardar_e_baixar(api_key, generation_id):
    prazo_final = time.time() + TIMEOUT_POLLING_SEGUNDOS
    while time.time() < prazo_final:
        time.sleep(INTERVALO_POLLING_SEGUNDOS)
        resp = requests.get(
            f'{BASE_URL}/generations/{generation_id}',
            headers=_headers(api_key),
            timeout=TIMEOUT_REQUEST,
        )
        resp.raise_for_status()
        dados = resp.json()
        status, urls = _extrair_status_e_urls(dados)

        if status in ('FAILED', 'ERROR'):
            raise LeonardoError(f'Geração falhou no Leonardo.Ai: {resp.text[:500]}')
        if status in ('COMPLETE', 'COMPLETED') and urls:
            imagem_resp = requests.get(urls[0], timeout=TIMEOUT_REQUEST)
            imagem_resp.raise_for_status()
            mime_saida = imagem_resp.headers.get('Content-Type', 'image/jpeg').split(';')[0]
            return imagem_resp.content, mime_saida

    raise LeonardoError('Tempo esgotado esperando a geração no Leonardo.Ai.')


def gerar_imagem_leonardo(prompt, foto_bytes, mime_type, api_key):
    """
    Gera a imagem promocional usando a foto real do veículo como referência.
    Retorna (bytes, mime_type) ou levanta LeonardoError com uma mensagem
    amigável — o caller (ai_promocional.py) decide como logar/propagar.
    """
    image_id = _upload_foto_referencia(api_key, foto_bytes, mime_type)
    generation_id = _criar_generation(api_key, prompt, image_id)
    return _aguardar_e_baixar(api_key, generation_id)
