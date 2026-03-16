from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import WhatsAppConversation, WhatsAppInstance, WhatsAppMessage

logger = logging.getLogger(__name__)


def normalize_wa_id(raw_value: str) -> str:
    value = (raw_value or '').strip()
    if '@' in value:
        return value
    if not value:
        return value
    digits = re.sub(r'\D', '', value)
    return f'{digits}@s.whatsapp.net' if digits else value


def normalize_number(raw_value: str) -> str:
    return re.sub(r'\D', '', raw_value or '')


def parse_message_text(payload: dict[str, Any]) -> str:
    data = payload.get('data', payload)
    message = data.get('message', {}) if isinstance(data, dict) else {}
    if not isinstance(message, dict):
        return str(message)

    if message.get('conversation'):
        return message.get('conversation')
    if message.get('extendedTextMessage', {}).get('text'):
        return message['extendedTextMessage']['text']
    if message.get('imageMessage', {}).get('caption'):
        return message['imageMessage']['caption']
    if message.get('videoMessage', {}).get('caption'):
        return message['videoMessage']['caption']

    return data.get('text') or data.get('body') or ''


def parse_message_timestamp(payload: dict[str, Any]) -> datetime:
    data = payload.get('data', payload)
    raw_ts = (
        data.get('messageTimestamp')
        or data.get('message', {}).get('messageTimestamp')
        or data.get('timestamp')
    )

    if isinstance(raw_ts, (int, float)):
        return datetime.fromtimestamp(int(raw_ts), tz=timezone.get_current_timezone())
    if isinstance(raw_ts, str):
        parsed = parse_datetime(raw_ts)
        if parsed:
            return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)

    return timezone.now()


def resolve_contact_name(payload: dict[str, Any], data: dict[str, Any]) -> str:
    return (
        data.get('pushName')
        or data.get('notifyName')
        or payload.get('senderName')
        or payload.get('contactName')
        or ''
    )


@dataclass
class EvolutionAPIClient:
    instance: WhatsAppInstance

    @property
    def base_url(self) -> str:
        return self.instance.api_base_url.rstrip('/')

    @property
    def headers(self) -> dict[str, str]:
        return {
            'apikey': self.instance.api_key,
            'Content-Type': 'application/json',
        }

    def send_text(self, number: str, text: str) -> dict[str, Any]:
        url = f'{self.base_url}/message/sendText/{self.instance.instance_name}'
        payload = {'number': normalize_number(number), 'text': text}
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json() if response.content else {}

    def connection_state(self) -> dict[str, Any]:
        url = f'{self.base_url}/instance/connectionState/{self.instance.instance_name}'
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json() if response.content else {}


def get_active_instance() -> WhatsAppInstance | None:
    instance = WhatsAppInstance.objects.filter(ativo=True).order_by('-atualizado_em').first()
    if instance:
        return instance

    env_base_url = getattr(settings, 'EVOLUTION_API_URL', '') or ''
    env_api_key = getattr(settings, 'EVOLUTION_API_KEY', '') or ''
    env_instance = getattr(settings, 'EVOLUTION_INSTANCE', '') or ''
    if env_base_url and env_api_key and env_instance:
        return WhatsAppInstance(
            nome='Ambiente',
            api_base_url=env_base_url,
            api_key=env_api_key,
            instance_name=env_instance,
            ativo=True,
        )
    return None


def process_webhook_payload(payload: dict[str, Any], instance: WhatsAppInstance | None = None) -> None:
    data = payload.get('data', payload)
    if not isinstance(data, dict):
        return

    key_data = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
    remote_jid = (
        key_data.get('remoteJid')
        or data.get('remoteJid')
        or data.get('from')
        or data.get('sender')
    )
    wa_id = normalize_wa_id(remote_jid)
    if not wa_id:
        return

    from_me = bool(
        key_data.get('fromMe')
        or data.get('fromMe')
        or payload.get('fromMe')
    )
    direction = WhatsAppMessage.Direction.ENVIADA if from_me else WhatsAppMessage.Direction.RECEBIDA

    contato = resolve_contact_name(payload, data)
    texto = parse_message_text(payload)
    ts = parse_message_timestamp(payload)
    ext_id = (
        key_data.get('id')
        or data.get('id')
        or payload.get('id')
    )

    conversation, _ = WhatsAppConversation.objects.get_or_create(
        wa_id=wa_id,
        defaults={
            'instance': instance if instance and instance.pk else None,
            'nome_contato': contato,
            'e_grupo': wa_id.endswith('@g.us'),
            'ultima_mensagem': texto,
            'ultima_mensagem_em': ts,
            'metadata': payload,
        },
    )

    if instance and instance.pk and not conversation.instance:
        conversation.instance = instance
    if contato and not conversation.nome_contato:
        conversation.nome_contato = contato
    conversation.ultima_mensagem = texto[:500]
    conversation.ultima_mensagem_em = ts
    conversation.metadata = payload
    if direction == WhatsAppMessage.Direction.RECEBIDA:
        conversation.nao_lidas = (conversation.nao_lidas or 0) + 1
    conversation.save()

    defaults = {
        'conversa': conversation,
        'direcao': direction,
        'conteudo': texto,
        'status': WhatsAppMessage.Status.ENTREGUE if from_me else WhatsAppMessage.Status.LIDA,
        'payload': payload,
        'recebido_em': ts if direction == WhatsAppMessage.Direction.RECEBIDA else None,
    }

    if ext_id:
        WhatsAppMessage.objects.update_or_create(external_id=ext_id, defaults=defaults)
    else:
        WhatsAppMessage.objects.create(**defaults)

    logger.info('Webhook WhatsApp processado: %s', conversation.wa_id)
