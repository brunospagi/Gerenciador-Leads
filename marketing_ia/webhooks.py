import logging

import requests

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 8


def montar_payload(post):
    anuncio = post.anuncio
    return {
        'evento': 'post_promocional',
        'post_id': post.pk,
        'imagem_url': post.imagem.url,
        'legenda': post.legenda,
        'hashtags': post.hashtags or '',
        'veiculo': {
            'titulo': anuncio.titulo,
            'marca': anuncio.marca,
            'modelo': anuncio.modelo,
            'ano': anuncio.ano,
            'preco': str(anuncio.preco) if anuncio.preco else None,
            'url_anuncio': anuncio.url,
        },
    }


def enviar_post_webhook(post, webhook):
    """
    Envia o post (link da imagem no S3/MinIO + legenda) para a URL do webhook.
    Retorna um dict {'sucesso': bool, 'status_code': int|None, 'erro': str|None}
    — nunca levanta exceção, para o caller sempre poder registrar o resultado.
    """
    payload = montar_payload(post)
    try:
        response = requests.post(webhook.url, json=payload, timeout=WEBHOOK_TIMEOUT_SECONDS)
        response.raise_for_status()
        return {'sucesso': True, 'status_code': response.status_code, 'erro': None}
    except requests.exceptions.RequestException as exc:
        status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
        logger.warning('Falha ao enviar post %s para webhook %s: %s', post.pk, webhook.pk, exc)
        return {'sucesso': False, 'status_code': status_code, 'erro': str(exc)[:255]}


def montar_payload_combinado(post):
    return {
        'evento': 'post_combinado',
        'post_id': post.pk,
        'imagem_url': post.imagem.url,
        'legenda': post.legenda,
        'hashtags': post.hashtags or '',
        'quantidade': post.quantidade,
        'criterio': post.criterio,
        'veiculos': [
            {
                'titulo': veiculo.titulo,
                'marca': veiculo.marca,
                'modelo': veiculo.modelo,
                'ano': veiculo.ano,
                'preco': str(veiculo.preco) if veiculo.preco else None,
                'url_anuncio': veiculo.url,
            }
            for veiculo in post.veiculos.all()
        ],
    }


def enviar_post_combinado_webhook(post, webhook):
    """Mesma lógica de enviar_post_webhook, só que pro payload com a lista de
    veículos do combinado em vez de um único 'veiculo'."""
    payload = montar_payload_combinado(post)
    try:
        response = requests.post(webhook.url, json=payload, timeout=WEBHOOK_TIMEOUT_SECONDS)
        response.raise_for_status()
        return {'sucesso': True, 'status_code': response.status_code, 'erro': None}
    except requests.exceptions.RequestException as exc:
        status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
        logger.warning('Falha ao enviar combinado %s para webhook %s: %s', post.pk, webhook.pk, exc)
        return {'sucesso': False, 'status_code': status_code, 'erro': str(exc)[:255]}
