import logging

import webpush

from .models import Notificacao

logger = logging.getLogger(__name__)


def notificar_usuario(usuario, mensagem, url=None, titulo="Nova notificação"):
    """Cria uma notificação in-app e tenta enviar push web para o usuário."""
    Notificacao.objects.create(usuario=usuario, mensagem=mensagem, url=url or '')

    try:
        payload = {
            "head": titulo,
            "body": mensagem,
            "icon": "/static/images/logo-spagi-192x192.png",
            "url": url or "/notificacoes/",
        }
        webpush.send_user_notification(user=usuario, payload=payload, ttl=1000)
    except Exception as e:
        # Usuário pode não ter nenhum dispositivo inscrito em push; a notificação
        # in-app já foi salva, então isso não deve interromper o fluxo do chamador.
        logger.warning("Erro ao enviar Push Notification para %s: %s", usuario.username, e)
