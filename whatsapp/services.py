from __future__ import annotations

import logging
import re
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import WhatsAppConversation, WhatsAppInstance, WhatsAppMessage

logger = logging.getLogger(__name__)


def sanitize_text_content(value: str) -> str:
    text = str(value or '')
    # Remove caracteres invisiveis que podem gerar bolhas "vazias"
    text = re.sub(r'[\u200b\u200c\u200d\ufeff\u200e\u200f]', '', text)
    return text.strip()


def normalize_wa_id(raw_value: str) -> str:
    value = (raw_value or '').strip()
    if not value:
        return value

    # Normaliza sufixos comuns da Evolution/WhatsApp para evitar duplicidade de conversa
    value = value.lower()
    value = value.replace('@c.us', '@s.whatsapp.net')

    if '@' in value:
        local, domain = value.split('@', 1)
        # Remove sufixo de dispositivo/session (ex.: 5511999999999:16@s.whatsapp.net)
        local = local.split(':', 1)[0]
        local_digits = re.sub(r'\D', '', local)
        if domain in {'s.whatsapp.net', 'lid', 'g.us', 'broadcast'}:
            if domain == 's.whatsapp.net' and local_digits:
                return f'{local_digits}@s.whatsapp.net'
            if domain == 'lid' and local:
                return f'{local}@lid'
            return f'{local}@{domain}'
        # Mantem dominio desconhecido, mas com local sanitizado
        return f'{local_digits or local}@{domain}'

    digits = re.sub(r'\D', '', value)
    return f'{digits}@s.whatsapp.net' if digits else value


def is_lid_jid(jid: str) -> bool:
    return (jid or '').strip().lower().endswith('@lid')


def is_real_number_jid(jid: str) -> bool:
    candidate = (jid or '').strip().lower()
    return bool(re.match(r'^\d+@s\.whatsapp\.net$', candidate))


def normalize_number(raw_value: str) -> str:
    return re.sub(r'\D', '', raw_value or '')


def resolve_avatar_url(payload: dict[str, Any], data: dict[str, Any]) -> str:
    candidates = [
        data.get('profilePicUrl'),
        data.get('profilePictureUrl'),
        data.get('picture'),
        data.get('avatarUrl'),
        payload.get('profilePicUrl'),
        payload.get('profilePictureUrl'),
        payload.get('avatarUrl'),
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def extract_jid_candidates(payload: dict[str, Any], data: dict[str, Any], key_data: dict[str, Any]) -> list[str]:
    candidates = [
        key_data.get('remoteJid'),
        key_data.get('participant'),
        data.get('remoteJid'),
        data.get('from'),
        data.get('sender'),
        data.get('participant'),
        payload.get('remoteJid'),
        payload.get('from'),
        payload.get('sender'),
    ]
    result = []
    for value in candidates:
        if isinstance(value, str) and value.strip():
            normalized = normalize_wa_id(value.strip())
            if normalized and normalized not in result:
                result.append(normalized)
    return result


def _extract_self_jids(payload: dict[str, Any], data: dict[str, Any], instance: WhatsAppInstance | None) -> set[str]:
    candidates: list[str] = []

    source_dicts = [payload, data]
    instance_data = data.get('instance') if isinstance(data.get('instance'), dict) else {}
    if instance_data:
        source_dicts.append(instance_data)

    for source in source_dicts:
        if not isinstance(source, dict):
            continue
        for key in (
            'me',
            'myJid',
            'myid',
            'owner',
            'ownerJid',
            'jid',
            'wid',
            'number',
        ):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
            elif isinstance(value, dict):
                for nested_key in ('id', 'jid', 'wid', 'number', 'user'):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, str) and nested_value.strip():
                        candidates.append(nested_value.strip())

    normalized: set[str] = set()
    for value in candidates:
        jid = normalize_wa_id(value)
        if jid:
            normalized.add(jid)
            if '@' in jid:
                base = jid.split('@', 1)[0]
                if base:
                    normalized.add(f'{base}@s.whatsapp.net')
    return normalized


def _choose_conversation_jid(
    *,
    jid_candidates: list[str],
    from_me: bool,
    self_jids: set[str],
) -> tuple[str, str, str]:
    filtered = [jid for jid in jid_candidates if jid and jid not in self_jids]
    base = filtered if filtered else jid_candidates

    real_jid = next((jid for jid in base if is_real_number_jid(jid)), '')
    lid_jid = next((jid for jid in base if is_lid_jid(jid)), '')
    wa_id = real_jid or lid_jid or (base[0] if base else '')

    # Para mensagens enviadas pelo proprio aparelho, sempre prioriza o destinatario (nao-eu)
    if from_me and filtered:
        real_filtered = next((jid for jid in filtered if is_real_number_jid(jid)), '')
        lid_filtered = next((jid for jid in filtered if is_lid_jid(jid)), '')
        wa_id = real_filtered or lid_filtered or filtered[0]
        if real_filtered:
            real_jid = real_filtered
        if lid_filtered:
            lid_jid = lid_filtered

    return wa_id, real_jid, lid_jid


def normalize_labels(raw_labels: Any) -> list[str]:
    labels: list[str] = []
    if isinstance(raw_labels, list):
        for item in raw_labels:
            if isinstance(item, str):
                value = item.strip()
                if value:
                    labels.append(value)
            elif isinstance(item, dict):
                value = (
                    item.get('name')
                    or item.get('label')
                    or item.get('title')
                    or item.get('id')
                )
                if value:
                    labels.append(str(value).strip())
    elif isinstance(raw_labels, dict):
        value = raw_labels.get('name') or raw_labels.get('label') or raw_labels.get('title') or raw_labels.get('id')
        if value:
            labels.append(str(value).strip())
    elif isinstance(raw_labels, str):
        value = raw_labels.strip()
        if value:
            labels.append(value)

    # Remove duplicadas mantendo ordem
    unique_labels = []
    for label in labels:
        if label and label not in unique_labels:
            unique_labels.append(label)
    return unique_labels


def extract_labels(payload: dict[str, Any], data: dict[str, Any]) -> list[str]:
    candidates = [
        data.get('labels'),
        data.get('label'),
        data.get('tag'),
        data.get('tags'),
        payload.get('labels'),
        payload.get('label'),
        payload.get('tag'),
        payload.get('tags'),
    ]
    for raw in candidates:
        parsed = normalize_labels(raw)
        if parsed:
            return parsed

    # Alguns eventos trazem em estruturas aninhadas
    contact = data.get('contact')
    if isinstance(contact, dict):
        parsed = normalize_labels(contact.get('labels') or contact.get('tags'))
        if parsed:
            return parsed

    association = data.get('association')
    if isinstance(association, dict):
        parsed = normalize_labels(association.get('labels') or association.get('tags'))
        if parsed:
            return parsed

    return []


def parse_message_text(payload: dict[str, Any]) -> str:
    data = payload.get('data', payload)
    message = data.get('message', {}) if isinstance(data, dict) else {}
    if not isinstance(message, dict):
        return str(message)

    if message.get('conversation'):
        return sanitize_text_content(message.get('conversation'))
    if message.get('extendedTextMessage', {}).get('text'):
        return sanitize_text_content(message['extendedTextMessage']['text'])
    if message.get('imageMessage', {}).get('caption'):
        return sanitize_text_content(message['imageMessage']['caption'])
    if message.get('videoMessage', {}).get('caption'):
        return sanitize_text_content(message['videoMessage']['caption'])

    return sanitize_text_content(data.get('text') or data.get('body') or '')


def parse_message_media(payload: dict[str, Any]) -> tuple[str, str]:
    data = payload.get('data', payload)
    message = data.get('message', {}) if isinstance(data, dict) else {}
    if not isinstance(message, dict):
        return '', ''

    mapping = [
        ('imageMessage', 'image'),
        ('videoMessage', 'video'),
        ('audioMessage', 'audio'),
        ('documentMessage', 'document'),
    ]
    for field, media_kind in mapping:
        media_obj = message.get(field)
        if isinstance(media_obj, dict):
            media_url = (
                media_obj.get('url')
                or media_obj.get('directPath')
                or media_obj.get('mediaUrl')
                or ''
            )
            if media_url:
                return str(media_url), media_kind

            mime = (
                media_obj.get('mimetype')
                or media_obj.get('mimeType')
                or data.get('mimetype')
                or data.get('mimeType')
                or payload.get('mimetype')
                or payload.get('mimeType')
                or ''
            )
            base64_data = (
                media_obj.get('base64')
                or data.get('base64')
                or payload.get('base64')
                or ''
            )
            if base64_data and isinstance(base64_data, str):
                mime_val = str(mime or 'application/octet-stream')
                return f'data:{mime_val};base64,{base64_data}', media_kind

    # Fallback: algumas versoes enviam URL fora de message.{image,video,...}
    generic_url = (
        data.get('mediaUrl')
        or data.get('url')
        or data.get('media')
        or data.get('fileUrl')
        or payload.get('mediaUrl')
        or payload.get('url')
        or payload.get('media')
        or ''
    )
    if generic_url:
        mime = str(
            data.get('mimetype')
            or data.get('mimeType')
            or payload.get('mimetype')
            or payload.get('mimeType')
            or ''
        ).lower()
        msg_type = str(data.get('messageType') or payload.get('messageType') or '').lower()
        if mime.startswith('image/') or 'image' in msg_type:
            return str(generic_url), 'image'
        if mime.startswith('video/') or 'video' in msg_type:
            return str(generic_url), 'video'
        if mime.startswith('audio/') or 'audio' in msg_type or 'ptt' in msg_type:
            return str(generic_url), 'audio'
        return str(generic_url), 'document'

    return '', ''


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


def _find_nested_value(payload: Any, target_keys: set[str]) -> str:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key or '').strip().lower()
            if normalized_key in target_keys and value is not None:
                if isinstance(value, (str, int, float)):
                    text = str(value).strip()
                    if text:
                        return text
            found = _find_nested_value(value, target_keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_nested_value(item, target_keys)
            if found:
                return found
    return ''


def detect_facebook_ads_origin(payload: dict[str, Any], data: dict[str, Any]) -> tuple[bool, dict[str, str]]:
    text_blob = ''
    try:
        text_blob = json.dumps(payload or {}, ensure_ascii=False).lower()
    except Exception:
        text_blob = str(payload or '').lower()

    indicators = [
        'facebook.com',
        'm.facebook.com',
        'fbclid',
        'utm_source=facebook',
        '"utm_source":"facebook',
        'click_to_whatsapp',
        'ctwa',
        'lead_ads',
        'leadads',
    ]
    has_indicator = any(marker in text_blob for marker in indicators)

    key_data = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
    message = data.get('message', {}) if isinstance(data.get('message'), dict) else {}
    context_info = message.get('extendedTextMessage', {}).get('contextInfo', {}) if isinstance(
        message.get('extendedTextMessage'), dict
    ) else {}

    search_space = {
        'payload': payload,
        'data': data,
        'key': key_data,
        'message': message,
        'context_info': context_info,
    }
    search_keys = {
        'source',
        'sourceid',
        'source_id',
        'adid',
        'ad_id',
        'adsetid',
        'adset_id',
        'campaignid',
        'campaign_id',
        'fbclid',
        'utm_source',
        'utm_campaign',
        'ref',
        'externaladreply',
        'ctwa',
    }

    source = _find_nested_value(search_space, {'source', 'utm_source'}) or ''
    fbclid = _find_nested_value(search_space, {'fbclid'}) or ''
    campaign_id = _find_nested_value(search_space, {'campaignid', 'campaign_id'}) or ''
    adset_id = _find_nested_value(search_space, {'adsetid', 'adset_id'}) or ''
    ad_id = _find_nested_value(search_space, {'adid', 'ad_id'}) or ''
    source_id = _find_nested_value(search_space, {'sourceid', 'source_id'}) or ''
    ref = _find_nested_value(search_space, {'ref'}) or ''
    ad_link = _find_nested_value(search_space, {'url', 'link', 'adlink', 'ad_link', 'sourceurl', 'source_url'}) or ''

    metadata = {
        'source': source,
        'fbclid': fbclid,
        'campaign_id': campaign_id,
        'adset_id': adset_id,
        'ad_id': ad_id,
        'source_id': source_id,
        'ref': ref,
        'ad_link': ad_link,
    }
    metadata = {k: v for k, v in metadata.items() if v}

    lower_source = (source or '').strip().lower()
    lower_ref = (ref or '').strip().lower()
    source_looks_facebook = any(
        token in lower_source for token in ['facebook', 'meta', 'instagram', 'ctwa', 'click_to_whatsapp']
    ) or any(token in lower_ref for token in ['facebook', 'meta', 'instagram', 'ctwa', 'click_to_whatsapp'])
    has_fbclid = bool(fbclid)
    has_ad_ids = bool(campaign_id or adset_id or ad_id or source_id)

    has_metadata_hint = bool(_find_nested_value(search_space, search_keys))
    matched = has_indicator or has_fbclid or source_looks_facebook or (has_ad_ids and has_metadata_hint)
    return matched, metadata


def _build_ads_system_message(ads_metadata: dict[str, str]) -> str:
    source = ads_metadata.get('source') or 'Facebook Ads'
    campaign = ads_metadata.get('campaign_id') or '-'
    adset = ads_metadata.get('adset_id') or '-'
    ad_id = ads_metadata.get('ad_id') or '-'
    fbclid = ads_metadata.get('fbclid') or '-'
    ref = ads_metadata.get('ref') or '-'
    ad_link = ads_metadata.get('ad_link') or '-'
    return (
        'Lead de anuncio detectado.\n'
        f'Origem: {source}\n'
        f'Campanha: {campaign}\n'
        f'Conjunto: {adset}\n'
        f'Anuncio: {ad_id}\n'
        f'fbclid: {fbclid}\n'
        f'Referencia: {ref}\n'
        f'Link do anuncio: {ad_link}'
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

    def send_media(
        self,
        number: str,
        media_url: str,
        mediatype: str,
        mimetype: str,
        caption: str = '',
        file_name: str = '',
    ) -> dict[str, Any]:
        url = f'{self.base_url}/message/sendMedia/{self.instance.instance_name}'
        payload = {
            'number': normalize_number(number),
            'mediatype': mediatype,
            'mimetype': mimetype,
            'caption': caption or '',
            'media': media_url,
        }
        if file_name:
            payload['fileName'] = file_name
        response = requests.post(url, json=payload, headers=self.headers, timeout=60)
        response.raise_for_status()
        return response.json() if response.content else {}

    def send_whatsapp_audio(self, number: str, audio_url: str) -> dict[str, Any]:
        url = f'{self.base_url}/message/sendWhatsAppAudio/{self.instance.instance_name}'
        payload = {
            'number': normalize_number(number),
            'audio': audio_url,
        }
        response = requests.post(url, json=payload, headers=self.headers, timeout=60)
        response.raise_for_status()
        return response.json() if response.content else {}

    def send_reaction(self, remote_jid: str, from_me: bool, message_id: str, reaction: str) -> dict[str, Any]:
        url = f'{self.base_url}/message/sendReaction/{self.instance.instance_name}'
        payload = {
            'key': {
                'remoteJid': remote_jid,
                'fromMe': bool(from_me),
                'id': message_id,
            },
            'reaction': reaction,
        }
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json() if response.content else {}

    def create_instance(self, qrcode: bool = True, integration: str = 'WHATSAPP-BAILEYS') -> dict[str, Any]:
        url = f'{self.base_url}/instance/create'
        payload = {
            'instanceName': self.instance.instance_name,
            'qrcode': qrcode,
            'integration': integration,
        }
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json() if response.content else {}

    def set_webhook(
        self,
        webhook_url: str,
        events: list[str] | None = None,
        webhook_secret: str = '',
    ) -> dict[str, Any]:
        url = f'{self.base_url}/webhook/set/{self.instance.instance_name}'
        selected_events = events or [
            'QRCODE_UPDATED',
            'MESSAGES_UPSERT',
            'MESSAGES_UPDATE',
            'SEND_MESSAGE',
            'CONNECTION_UPDATE',
            'PRESENCE_UPDATE',
            'PRESENCE_UPSERT',
            'LABELS_ASSOCIATION',
            'LABELS_EDIT',
            'CONTACTS_UPDATE',
        ]
        headers = {'Content-Type': 'application/json'}
        if webhook_secret:
            headers['X-Webhook-Secret'] = webhook_secret
        payload = {
            'webhook': {
                'enabled': True,
                'url': webhook_url,
                'headers': headers,
                'byEvents': True,
                'base64': True,
                'events': selected_events,
            }
        }
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json() if response.content else {}

    def connect_instance(self, number: str = '') -> dict[str, Any]:
        url = f'{self.base_url}/instance/connect/{self.instance.instance_name}'
        params = {}
        if number:
            params['number'] = normalize_number(number)
        response = requests.get(url, params=params, headers=self.headers, timeout=30)
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


def extract_qr_base64(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ''

    direct = payload.get('base64')
    if isinstance(direct, str) and direct:
        return direct

    qrcode = payload.get('qrcode')
    if isinstance(qrcode, dict):
        qr_val = qrcode.get('base64') or qrcode.get('code')
        if isinstance(qr_val, str):
            return qr_val

    data = payload.get('data')
    if isinstance(data, dict):
        qr_val = data.get('base64')
        if isinstance(qr_val, str):
            return qr_val

    return ''


def map_delivery_status(payload: dict[str, Any]) -> str:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}

    raw_status = (
        data.get('status')
        or data.get('messageStatus')
        or data.get('update', {}).get('status')
        or payload.get('status')
        or ''
    )
    raw_status_str = str(raw_status).strip().lower()
    status_map = {
        'sent': WhatsAppMessage.Status.ENVIADA,
        'server_ack': WhatsAppMessage.Status.ENVIADA,
        'delivery_ack': WhatsAppMessage.Status.ENTREGUE,
        'delivered': WhatsAppMessage.Status.ENTREGUE,
        'read': WhatsAppMessage.Status.LIDA,
        'played': WhatsAppMessage.Status.LIDA,
        'failed': WhatsAppMessage.Status.FALHA,
        'error': WhatsAppMessage.Status.FALHA,
        'pending': WhatsAppMessage.Status.PENDENTE,
    }
    if raw_status_str in status_map:
        return status_map[raw_status_str]

    ack = data.get('ack')
    if ack is None:
        ack = payload.get('ack')
    try:
        ack = int(ack)
    except (TypeError, ValueError):
        ack = None

    if ack == -1:
        return WhatsAppMessage.Status.FALHA
    if ack == 0:
        return WhatsAppMessage.Status.PENDENTE
    if ack == 1:
        return WhatsAppMessage.Status.ENVIADA
    if ack == 2:
        return WhatsAppMessage.Status.ENTREGUE
    if ack in {3, 4}:
        return WhatsAppMessage.Status.LIDA

    return WhatsAppMessage.Status.ENVIADA


def process_status_update(payload: dict[str, Any]) -> bool:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    key_data = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
    external_id = (
        key_data.get('id')
        or data.get('id')
        or data.get('messageId')
        or payload.get('id')
    )
    if not external_id:
        return False

    status = map_delivery_status(payload)
    message = WhatsAppMessage.objects.filter(external_id=external_id).first()
    if not message:
        return False

    merged_payload = dict(message.payload or {})
    merged_payload['status_update'] = payload
    message.status = status
    message.payload = merged_payload
    message.save(update_fields=['status', 'payload'])
    return True


def process_connection_update(payload: dict[str, Any], instance: WhatsAppInstance | None) -> bool:
    if not instance:
        return False
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    raw_state = (
        data.get('state')
        or data.get('connection')
        or data.get('status')
        or data.get('instance', {}).get('state')
        or data.get('instance', {}).get('status')
        or ''
    )
    if not raw_state:
        return False

    state = str(raw_state).strip().lower()
    instance.status_conexao = state
    merged = dict(instance.ultima_resposta or {})
    merged['connection_update'] = payload
    instance.ultima_resposta = merged
    instance.save(update_fields=['status_conexao', 'ultima_resposta', 'atualizado_em'])
    return True


def process_qrcode_update(payload: dict[str, Any], instance: WhatsAppInstance | None) -> bool:
    if not instance:
        return False

    qr = extract_qr_base64(payload)
    if not qr:
        return False

    instance.qr_code_base64 = qr
    merged = dict(instance.ultima_resposta or {})
    merged['qrcode_update'] = payload
    instance.ultima_resposta = merged
    instance.save(update_fields=['qr_code_base64', 'ultima_resposta', 'atualizado_em'])
    return True


def process_labels_update(payload: dict[str, Any]) -> bool:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    if isinstance(data, list):
        updated_any = False
        for item in data:
            if not isinstance(item, dict):
                continue
            nested_payload = dict(payload)
            nested_payload['data'] = item
            if process_labels_update(nested_payload):
                updated_any = True
        return updated_any
    if not isinstance(data, dict):
        return False
    key_data = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
    jid_candidates = extract_jid_candidates(payload, data if isinstance(data, dict) else {}, key_data)
    if not jid_candidates:
        return False
    self_jids = _extract_self_jids(payload, data if isinstance(data, dict) else {}, instance=None)
    from_me = bool(
        key_data.get('fromMe')
        or data.get('fromMe')
        or payload.get('fromMe')
    )

    labels = extract_labels(payload, data if isinstance(data, dict) else {})
    if not labels:
        return False

    wa_id, real_jid, lid_jid = _choose_conversation_jid(
        jid_candidates=jid_candidates,
        from_me=from_me,
        self_jids=self_jids,
    )

    conversation = None
    if real_jid:
        conversation = WhatsAppConversation.objects.filter(wa_id=real_jid).first()
    if not conversation and lid_jid:
        conversation = WhatsAppConversation.objects.filter(wa_id_alt=lid_jid).first()
    if not conversation:
        conversation = WhatsAppConversation.objects.filter(wa_id=wa_id).first()
    if not conversation:
        return False

    conversation.etiquetas = labels
    merged_meta = dict(conversation.metadata or {})
    merged_meta['labels_update'] = payload
    conversation.metadata = merged_meta
    conversation.save(update_fields=['etiquetas', 'metadata', 'atualizado_em'])
    return True


def _normalize_presence_state(raw_state: Any) -> str:
    state = str(raw_state or '').strip().lower()
    if not state:
        return ''
    if state in {'composing', 'typing'}:
        return 'typing'
    if state in {'recording', 'recordingaudio', 'recording_audio'}:
        return 'recording'
    if state in {'paused', 'available', 'unavailable', 'idle', 'stop'}:
        return ''
    return ''


def process_presence_update(payload: dict[str, Any], instance: WhatsAppInstance | None = None) -> bool:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return False

    self_jids = _extract_self_jids(payload, data, instance=instance)
    updates: list[tuple[str, str]] = []

    presences = data.get('presences')
    if isinstance(presences, dict):
        for jid_key, presence_info in presences.items():
            state = ''
            if isinstance(presence_info, dict):
                state = _normalize_presence_state(
                    presence_info.get('lastKnownPresence')
                    or presence_info.get('presence')
                    or presence_info.get('state')
                    or presence_info.get('status')
                )
            else:
                state = _normalize_presence_state(presence_info)
            updates.append((normalize_wa_id(str(jid_key or '')), state))
    elif isinstance(presences, list):
        for item in presences:
            if not isinstance(item, dict):
                continue
            jid = normalize_wa_id(str(item.get('id') or item.get('jid') or item.get('remoteJid') or ''))
            state = _normalize_presence_state(
                item.get('lastKnownPresence') or item.get('presence') or item.get('state') or item.get('status')
            )
            updates.append((jid, state))

    if not updates:
        key_data = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
        jid_candidates = extract_jid_candidates(payload, data, key_data)
        state = _normalize_presence_state(
            data.get('lastKnownPresence')
            or data.get('presence')
            or data.get('state')
            or data.get('status')
            or payload.get('presence')
            or payload.get('state')
        )
        for jid in jid_candidates:
            updates.append((jid, state))

    updated = False
    for jid, state in updates:
        if not jid or jid in self_jids:
            continue

        conversation = (
            WhatsAppConversation.objects.filter(wa_id=jid).first()
            or WhatsAppConversation.objects.filter(wa_id_alt=jid).first()
        )
        if not conversation:
            continue

        merged_meta = dict(conversation.metadata or {})
        merged_meta['presence'] = {
            'state': state,
            'updated_at': timezone.now().isoformat(),
        }
        conversation.metadata = merged_meta
        conversation.save(update_fields=['metadata', 'atualizado_em'])
        updated = True

    return updated


def process_webhook_payload(payload: dict[str, Any], instance: WhatsAppInstance | None = None) -> None:
    event_name = str(payload.get('event') or '').upper()
    event_name_norm = re.sub(r'[^A-Z0-9]+', '_', event_name).strip('_')
    if event_name_norm in {'PRESENCE_UPDATE', 'PRESENCE_UPSERT', 'PRESENCE'}:
        if process_presence_update(payload, instance=instance):
            logger.info('Webhook de presenca processado.')
            return
    if event_name_norm in {'LABELS_ASSOCIATION', 'LABELS_EDIT', 'CONTACTS_UPDATE'}:
        if process_labels_update(payload):
            logger.info('Webhook de etiquetas processado.')
            return
    if event_name_norm in {'CONNECTION_UPDATE', 'CONNECTION_STATE', 'INSTANCE_CONNECTION_UPDATE'}:
        if process_connection_update(payload, instance):
            logger.info('Webhook de conexao processado: %s', instance.instance_name if instance else '-')
            return

    if event_name_norm in {'QRCODE_UPDATED', 'QRCODE_UPDATE'}:
        if process_qrcode_update(payload, instance):
            logger.info('Webhook de QR code processado: %s', instance.instance_name if instance else '-')
            return

    if event_name_norm in {'MESSAGES_UPDATE', 'MESSAGE_UPDATE', 'MESSAGE_STATUS', 'SEND_MESSAGE'}:
        if process_status_update(payload):
            logger.info('Webhook de status processado para mensagem existente.')
        # Eventos de status nao devem criar conversa/mensagem nova
        return

    data = payload.get('data', payload)
    if not isinstance(data, dict):
        return

    key_data = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
    jid_candidates = extract_jid_candidates(payload, data, key_data)

    from_me = bool(
        key_data.get('fromMe')
        or data.get('fromMe')
        or payload.get('fromMe')
    )
    self_jids = _extract_self_jids(payload, data, instance=instance)
    wa_id, real_jid, lid_jid = _choose_conversation_jid(
        jid_candidates=jid_candidates,
        from_me=from_me,
        self_jids=self_jids,
    )
    if not wa_id:
        return
    direction = WhatsAppMessage.Direction.ENVIADA if from_me else WhatsAppMessage.Direction.RECEBIDA

    contato = resolve_contact_name(payload, data)
    if from_me:
        # Evita sobrescrever contato com o proprio nome em mensagens enviadas do celular.
        contato = ''
    avatar_url = resolve_avatar_url(payload, data)
    etiquetas = extract_labels(payload, data)
    is_facebook_ads, ads_metadata = detect_facebook_ads_origin(payload, data)
    if is_facebook_ads and 'facebook ads' not in {str(et).strip().lower() for et in etiquetas}:
        etiquetas.append('Facebook Ads')
    texto = parse_message_text(payload)
    media_url, media_kind = parse_message_media(payload)
    raw_message = data.get('message') if isinstance(data.get('message'), dict) else {}
    if not texto and not media_url:
        # Evita criar bolha vazia (apenas horario) quando webhook nao traz conteudo real.
        if isinstance(raw_message, dict) and raw_message:
            unsupported_type = next(iter(raw_message.keys()), '')
            if unsupported_type:
                texto = '[Mensagem nao suportada]'
        if not texto:
            return
    if not texto and media_kind in {'image', 'video', 'audio'}:
        label = {'image': 'IMAGEM', 'video': 'VIDEO', 'audio': 'AUDIO'}.get(media_kind, media_kind.upper())
        texto = f'[{label}]'
    ts = parse_message_timestamp(payload)
    ext_id = (
        key_data.get('id')
        or data.get('id')
        or payload.get('id')
    )

    conversation = None
    if real_jid:
        conversation = WhatsAppConversation.objects.filter(wa_id=real_jid).first()
    if not conversation and lid_jid:
        conversation = WhatsAppConversation.objects.filter(wa_id_alt=lid_jid).first()
    if not conversation and lid_jid:
        conversation = WhatsAppConversation.objects.filter(wa_id=lid_jid).first()

    if not conversation:
        conversation = WhatsAppConversation.objects.create(
            wa_id=wa_id,
            wa_id_alt=lid_jid if (lid_jid and lid_jid != wa_id) else '',
            instance=instance if instance and instance.pk else None,
            nome_contato=contato,
            avatar_url=avatar_url,
            etiquetas=etiquetas,
            e_grupo=wa_id.endswith('@g.us'),
            ultima_mensagem=texto,
            ultima_mensagem_em=ts,
            metadata=payload,
        )
    else:
        if real_jid and conversation.wa_id != real_jid:
            collision = WhatsAppConversation.objects.filter(wa_id=real_jid).exclude(pk=conversation.pk).exists()
            if not collision:
                old_wa_id = conversation.wa_id
                conversation.wa_id = real_jid
                if is_lid_jid(old_wa_id) and not conversation.wa_id_alt:
                    conversation.wa_id_alt = old_wa_id
        if lid_jid and not conversation.wa_id_alt and lid_jid != conversation.wa_id:
            conversation.wa_id_alt = lid_jid

    if instance and instance.pk and not conversation.instance:
        conversation.instance = instance
    if contato and not conversation.nome_contato:
        conversation.nome_contato = contato
    if avatar_url:
        conversation.avatar_url = avatar_url
    if etiquetas:
        conversation.etiquetas = etiquetas
    conversation.ultima_mensagem = texto[:500]
    conversation.ultima_mensagem_em = ts
    conversation.metadata = payload
    if direction == WhatsAppMessage.Direction.RECEBIDA:
        conversation.nao_lidas = (conversation.nao_lidas or 0) + 1
    create_ads_notice = False
    if is_facebook_ads:
        merged_meta = dict(conversation.metadata or {})
        previous_ads_data = (
            merged_meta.get('facebook_ads', {}).get('data', {})
            if isinstance(merged_meta.get('facebook_ads'), dict)
            else {}
        )
        if ads_metadata and ads_metadata != previous_ads_data:
            create_ads_notice = True
        merged_meta['facebook_ads'] = {
            'detected': True,
            'captured_at': timezone.now().isoformat(),
            'data': ads_metadata,
        }
        conversation.metadata = merged_meta
    conversation.save()

    if is_facebook_ads and create_ads_notice:
        WhatsAppMessage.objects.create(
            conversa=conversation,
            direcao=WhatsAppMessage.Direction.SISTEMA,
            conteudo=_build_ads_system_message(ads_metadata),
            status=WhatsAppMessage.Status.ENTREGUE,
            payload={'facebook_ads_notice': ads_metadata},
        )

    defaults = {
        'conversa': conversation,
        'direcao': direction,
        'conteudo': texto,
        'media_url': media_url or '',
        'status': WhatsAppMessage.Status.ENTREGUE if from_me else WhatsAppMessage.Status.LIDA,
        'payload': payload,
        'recebido_em': ts if direction == WhatsAppMessage.Direction.RECEBIDA else None,
    }

    if ext_id:
        WhatsAppMessage.objects.update_or_create(external_id=ext_id, defaults=defaults)
    else:
        WhatsAppMessage.objects.create(**defaults)

    logger.info('Webhook WhatsApp processado: %s', conversation.wa_id)
