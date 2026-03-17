from __future__ import annotations

import logging
import re
import json
import base64
import binascii
import mimetypes
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import F
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from crmspagi.storage_backends import PublicMediaStorage
from .models import WhatsAppConversation, WhatsAppInstance, WhatsAppMessage

logger = logging.getLogger(__name__)


def sanitize_text_content(value: str) -> str:
    text = str(value or '')
    # Remove caracteres invisiveis que podem gerar bolhas "vazias"
    text = re.sub(r'[\u200b\u200c\u200d\ufeff\u200e\u200f]', '', text)
    return text.strip()


def normalize_message_id(value: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    return re.sub(r'[^A-Za-z0-9]', '', raw).upper()


def resolve_message_by_external_candidates(candidates: list[str]) -> WhatsAppMessage | None:
    cleaned = []
    for raw in candidates:
        value = str(raw or '').strip()
        if not value:
            continue
        if value not in cleaned:
            cleaned.append(value)
        if ':' in value:
            base = value.split(':', 1)[0].strip()
            if base and base not in cleaned:
                cleaned.append(base)

    for candidate in cleaned:
        obj = WhatsAppMessage.objects.filter(external_id=candidate).first()
        if obj:
            return obj

    for candidate in cleaned:
        obj = WhatsAppMessage.objects.filter(external_id__iendswith=candidate).first()
        if obj:
            return obj

    normalized_tail_candidates = []
    for candidate in cleaned:
        normalized = normalize_message_id(candidate)
        if normalized:
            normalized_tail_candidates.append(normalized[-20:])

    if not normalized_tail_candidates:
        return None

    recent = WhatsAppMessage.objects.exclude(external_id__isnull=True).exclude(external_id='').order_by('-criado_em')[:1200]
    for msg in recent:
        msg_norm = normalize_message_id(msg.external_id or '')
        if not msg_norm:
            continue
        for tail in normalized_tail_candidates:
            if tail and msg_norm.endswith(tail):
                return msg
    return None


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
    contact_data = data.get('contact') if isinstance(data.get('contact'), dict) else {}
    instance_contact = data.get('instance') if isinstance(data.get('instance'), dict) else {}
    candidates = [
        data.get('profilePicUrl'),
        data.get('profilePictureUrl'),
        data.get('profilePicture'),
        data.get('pictureUrl'),
        data.get('imgUrl'),
        data.get('picture'),
        data.get('avatarUrl'),
        contact_data.get('profilePicUrl'),
        contact_data.get('profilePictureUrl'),
        contact_data.get('profilePicture'),
        contact_data.get('picture'),
        contact_data.get('avatarUrl'),
        contact_data.get('imgUrl'),
        instance_contact.get('profilePicUrl'),
        instance_contact.get('profilePictureUrl'),
        payload.get('profilePicUrl'),
        payload.get('profilePictureUrl'),
        payload.get('profilePicture'),
        payload.get('pictureUrl'),
        payload.get('imgUrl'),
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


def resolve_from_me(
    payload: dict[str, Any],
    data: dict[str, Any],
    key_data: dict[str, Any],
    self_jids: set[str],
) -> bool:
    explicit = bool(
        key_data.get('fromMe')
        or data.get('fromMe')
        or payload.get('fromMe')
    )
    if explicit:
        return True

    candidate_values = [
        key_data.get('remoteJid'),
        key_data.get('participant'),
        key_data.get('sender'),
        data.get('remoteJid'),
        data.get('participant'),
        data.get('sender'),
        data.get('from'),
        payload.get('remoteJid'),
        payload.get('participant'),
        payload.get('sender'),
        payload.get('from'),
    ]
    normalized_candidates = {
        normalize_wa_id(str(value))
        for value in candidate_values
        if isinstance(value, str) and value.strip()
    }
    normalized_candidates.discard('')
    if normalized_candidates and normalized_candidates.issubset(self_jids):
        return True
    return False


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
    message = unwrap_message_content(message)
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
    if message.get('image', {}).get('caption'):
        return sanitize_text_content(message['image']['caption'])
    if message.get('video', {}).get('caption'):
        return sanitize_text_content(message['video']['caption'])

    return sanitize_text_content(data.get('text') or data.get('body') or '')


def parse_message_media(payload: dict[str, Any]) -> tuple[str, str]:
    data = payload.get('data', payload)
    message = data.get('message', {}) if isinstance(data, dict) else {}
    message = unwrap_message_content(message)
    if not isinstance(message, dict):
        return '', ''

    def _is_encrypted_media_ref(value: str) -> bool:
        candidate = str(value or '').strip().lower()
        if not candidate:
            return False
        return (
            '.enc' in candidate
            or candidate.startswith('/v/t62')
        )

    def _normalize_public_media_url(value: str) -> str:
        candidate = str(value or '').strip()
        if not candidate:
            return ''
        lower = candidate.lower()
        if lower.startswith('data:'):
            return candidate
        if candidate.startswith('//'):
            return f'https:{candidate}'
        if lower.startswith('http://') or lower.startswith('https://'):
            return candidate
        if candidate.startswith('/'):
            return f'https://mmg.whatsapp.net{candidate}'
        return candidate

    def _media_from_base64(mime_value: str, raw_value: Any, media_kind: str) -> str:
        if not isinstance(raw_value, str):
            return ''
        raw = raw_value.strip()
        if not raw:
            return ''
        mime = str(mime_value or 'application/octet-stream').strip()
        source_data = raw
        if raw.startswith('data:'):
            header, _, encoded = raw.partition(',')
            if ';base64' in header:
                mime = header[5:].split(';', 1)[0] or mime
                source_data = encoded

        try:
            sanitized = re.sub(r'\s+', '', source_data)
            if len(sanitized) % 4:
                sanitized += '=' * (4 - (len(sanitized) % 4))
            decoded = base64.b64decode(sanitized)
        except (binascii.Error, ValueError):
            return ''

        extension = mimetypes.guess_extension(mime.split(';', 1)[0].strip().lower() or '') or ''
        if not extension:
            extension = {
                'image': '.jpg',
                'video': '.mp4',
                'audio': '.ogg',
                'document': '.bin',
            }.get(media_kind or '', '.bin')
        unique_name = f'{uuid.uuid4().hex}{extension}'
        storage_path = f'whatsapp/webhook/{timezone.now().strftime("%Y/%m")}/{unique_name}'
        file_obj = ContentFile(decoded, name=unique_name)

        try:
            storage = PublicMediaStorage()
            saved_path = storage.save(storage_path, file_obj)
            logger.info('WhatsApp media base64 salva no MinIO: kind=%s path=%s', media_kind, saved_path)
            return storage.url(saved_path)
        except Exception as exc:
            logger.warning('Falha ao salvar media base64 no MinIO, tentando storage padrao: %s', exc)
            try:
                fallback_file_obj = ContentFile(decoded, name=unique_name)
                saved_path = default_storage.save(storage_path, fallback_file_obj)
                logger.info('WhatsApp media base64 salva no storage padrao: kind=%s path=%s', media_kind, saved_path)
                return default_storage.url(saved_path)
            except Exception as fallback_exc:
                logger.warning('Falha ao salvar media base64 no storage padrao, usando data URL: %s', fallback_exc)
                return f'data:{mime};base64,{source_data}'

    def _infer_kind_by_mime_or_type(raw_mime: str, raw_type: str, fallback: str = 'document') -> str:
        mime = str(raw_mime or '').lower()
        msg_type = str(raw_type or '').lower()
        if 'sticker' in msg_type:
            return 'sticker'
        if mime.startswith('image/') or 'image' in msg_type:
            return 'image'
        if mime.startswith('video/') or 'video' in msg_type:
            return 'video'
        if mime.startswith('audio/') or 'audio' in msg_type or 'ptt' in msg_type:
            return 'audio'
        if 'document' in msg_type or 'file' in msg_type:
            return 'document'
        return fallback

    def _deep_media_candidates(root: Any) -> list[dict[str, str]]:
        candidates: list[dict[str, str]] = []

        def walk(node: Any, parent_key: str = '') -> None:
            if isinstance(node, dict):
                raw_type = (
                    node.get('messageType')
                    or node.get('mediaType')
                    or node.get('type')
                    or parent_key
                    or ''
                )
                raw_mime = (
                    node.get('mimetype')
                    or node.get('mimeType')
                    or node.get('mediaMimeType')
                    or ''
                )
                url = str(
                    node.get('url')
                    or node.get('mediaUrl')
                    or node.get('fileUrl')
                    or node.get('directPath')
                    or ''
                ).strip()
                base64_data = (
                    node.get('base64')
                    or node.get('mediaBase64')
                    or node.get('fileBase64')
                    or ''
                )
                if url or (isinstance(base64_data, str) and base64_data.strip()):
                    candidates.append({
                        'url': url,
                        'base64': str(base64_data or '').strip(),
                        'mime': str(raw_mime or '').strip(),
                        'kind': _infer_kind_by_mime_or_type(raw_mime, raw_type, fallback='document'),
                    })

                for child_key, child_value in node.items():
                    walk(child_value, str(child_key or ''))
            elif isinstance(node, list):
                for item in node:
                    walk(item, parent_key)

        walk(root)
        return candidates

    mapping = [
        ('imageMessage', 'image'),
        ('videoMessage', 'video'),
        ('audioMessage', 'audio'),
        ('documentMessage', 'document'),
        ('stickerMessage', 'sticker'),
        ('image', 'image'),
        ('video', 'video'),
        ('audio', 'audio'),
        ('document', 'document'),
        ('sticker', 'sticker'),
    ]
    for field, media_kind in mapping:
        media_obj = message.get(field)
        if isinstance(media_obj, dict):
            media_url = str(
                media_obj.get('url')
                or media_obj.get('mediaUrl')
                or media_obj.get('fileUrl')
                or ''
            ).strip()

            mime = (
                media_obj.get('mimetype')
                or media_obj.get('mimeType')
                or data.get('mimetype')
                or data.get('mimeType')
                or payload.get('mimetype')
                or payload.get('mimeType')
                or ''
            )
            media_url = _normalize_public_media_url(media_url)
            base64_data = (
                media_obj.get('base64')
                or media_obj.get('mediaBase64')
                or media_obj.get('fileBase64')
                or data.get('base64')
                or data.get('mediaBase64')
                or data.get('fileBase64')
                or payload.get('base64')
                or payload.get('mediaBase64')
                or payload.get('fileBase64')
                or ''
            )
            if media_url and not _is_encrypted_media_ref(media_url):
                return media_url, media_kind

            persisted_url = _media_from_base64(str(mime or 'application/octet-stream'), base64_data, media_kind)
            if persisted_url:
                return persisted_url, media_kind

            # Fallback final: directPath pode vir como file.enc e nao eh renderizavel no browser.
            # Mantemos apenas se nao parecer referencia criptografada.
            direct_path = str(media_obj.get('directPath') or '').strip()
            direct_path = _normalize_public_media_url(direct_path)
            if direct_path and not _is_encrypted_media_ref(direct_path):
                return direct_path, media_kind

    # Fallback: algumas versoes enviam URL fora de message.{image,video,...}
    generic_url = str(
        data.get('mediaUrl')
        or data.get('url')
        or data.get('media')
        or data.get('fileUrl')
        or payload.get('mediaUrl')
        or payload.get('url')
        or payload.get('media')
        or ''
    ).strip()
    generic_url = _normalize_public_media_url(generic_url)
    if generic_url:
        mime = str(
            data.get('mimetype')
            or data.get('mimeType')
            or payload.get('mimetype')
            or payload.get('mimeType')
            or ''
        ).lower()
        msg_type = str(data.get('messageType') or payload.get('messageType') or '').lower()
        if not _is_encrypted_media_ref(generic_url):
            if 'sticker' in msg_type:
                return generic_url, 'sticker'
            if mime.startswith('image/') or 'image' in msg_type:
                return generic_url, 'image'
            if mime.startswith('video/') or 'video' in msg_type:
                return generic_url, 'video'
            if mime.startswith('audio/') or 'audio' in msg_type or 'ptt' in msg_type:
                return generic_url, 'audio'
            return generic_url, 'document'

        generic_base64 = (
            data.get('base64')
            or data.get('mediaBase64')
            or data.get('fileBase64')
            or payload.get('base64')
            or payload.get('mediaBase64')
            or payload.get('fileBase64')
            or ''
        )
        persisted_url = _media_from_base64(mime or 'application/octet-stream', generic_base64, 'document')
        if persisted_url:
            if mime.startswith('image/') or 'image' in msg_type:
                return persisted_url, 'image'
            if mime.startswith('video/') or 'video' in msg_type:
                return persisted_url, 'video'
            if mime.startswith('audio/') or 'audio' in msg_type or 'ptt' in msg_type:
                return persisted_url, 'audio'
            return persisted_url, 'document'

    # Fallback profundo: algumas versoes enviam midia em estruturas nao padrao.
    for candidate in _deep_media_candidates(data):
        candidate_kind = candidate.get('kind') or 'document'
        candidate_mime = candidate.get('mime') or 'application/octet-stream'
        candidate_url = _normalize_public_media_url(candidate.get('url') or '')
        candidate_b64 = candidate.get('base64') or ''
        if candidate_url and not _is_encrypted_media_ref(candidate_url):
            return candidate_url, candidate_kind
        if candidate_b64:
            persisted_url = _media_from_base64(candidate_mime, candidate_b64, candidate_kind)
            if persisted_url:
                return persisted_url, candidate_kind

    for candidate in _deep_media_candidates(payload):
        candidate_kind = candidate.get('kind') or 'document'
        candidate_mime = candidate.get('mime') or 'application/octet-stream'
        candidate_url = _normalize_public_media_url(candidate.get('url') or '')
        candidate_b64 = candidate.get('base64') or ''
        if candidate_url and not _is_encrypted_media_ref(candidate_url):
            return candidate_url, candidate_kind
        if candidate_b64:
            persisted_url = _media_from_base64(candidate_mime, candidate_b64, candidate_kind)
            if persisted_url:
                return persisted_url, candidate_kind

    return '', ''


def unwrap_message_content(message: Any, depth: int = 0) -> dict[str, Any]:
    if not isinstance(message, dict):
        return {}
    if depth > 6:
        return message

    wrapper_keys = [
        'ephemeralMessage',
        'viewOnceMessage',
        'viewOnceMessageV2',
        'viewOnceMessageV2Extension',
        'documentWithCaptionMessage',
        'editedMessage',
        'deviceSentMessage',
    ]
    for key in wrapper_keys:
        wrapper = message.get(key)
        if isinstance(wrapper, dict):
            nested = wrapper.get('message')
            if isinstance(nested, dict):
                return unwrap_message_content(nested, depth + 1)

    return message


def infer_message_kind(raw_message: dict[str, Any], data: dict[str, Any], payload: dict[str, Any]) -> str:
    if not isinstance(raw_message, dict):
        return ''

    kind_by_key = {
        'imageMessage': 'image',
        'videoMessage': 'video',
        'audioMessage': 'audio',
        'documentMessage': 'document',
        'stickerMessage': 'sticker',
        'reactionMessage': 'reaction',
        'protocolMessage': 'protocol',
        'senderKeyDistributionMessage': 'key_distribution',
        'pollUpdateMessage': 'poll_update',
    }
    for key, kind in kind_by_key.items():
        if key in raw_message:
            return kind

    msg_type = str(data.get('messageType') or payload.get('messageType') or '').strip().lower()
    if 'sticker' in msg_type:
        return 'sticker'
    if 'image' in msg_type:
        return 'image'
    if 'video' in msg_type:
        return 'video'
    if 'audio' in msg_type or 'ptt' in msg_type:
        return 'audio'
    if 'document' in msg_type or 'file' in msg_type:
        return 'document'
    if 'reaction' in msg_type:
        return 'reaction'
    return ''


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
    contact_data = data.get('contact') if isinstance(data.get('contact'), dict) else {}
    return (
        data.get('pushName')
        or data.get('notifyName')
        or data.get('name')
        or data.get('profileName')
        or contact_data.get('name')
        or contact_data.get('pushName')
        or contact_data.get('notifyName')
        or contact_data.get('shortName')
        or payload.get('senderName')
        or payload.get('contactName')
        or payload.get('pushName')
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

    def edit_message(self, remote_jid: str, from_me: bool, message_id: str, text: str) -> dict[str, Any]:
        payload_variants = [
            {
                'key': {
                    'remoteJid': remote_jid,
                    'fromMe': bool(from_me),
                    'id': message_id,
                },
                'text': text,
            },
            {
                'key': {
                    'remoteJid': remote_jid,
                    'fromMe': bool(from_me),
                    'id': message_id,
                },
                'message': text,
            },
        ]
        endpoint_variants = [
            f'{self.base_url}/message/editMessage/{self.instance.instance_name}',
            f'{self.base_url}/message/updateMessage/{self.instance.instance_name}',
            f'{self.base_url}/chat/updateMessage/{self.instance.instance_name}',
            f'{self.base_url}/message/edit/{self.instance.instance_name}',
        ]

        last_error = None
        for endpoint in endpoint_variants:
            for payload in payload_variants:
                try:
                    response = requests.post(endpoint, json=payload, headers=self.headers, timeout=30)
                    response.raise_for_status()
                    return response.json() if response.content else {}
                except requests.RequestException as exc:
                    last_error = exc
                    continue

        if last_error:
            raise last_error
        raise RuntimeError('Nao foi possivel editar a mensagem na Evolution API.')

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

    def find_messages(self, where: dict[str, Any], page: int = 1, offset: int = 20) -> dict[str, Any]:
        url = f'{self.base_url}/chat/findMessages/{self.instance.instance_name}'
        payload = {
            'where': where or {},
            'page': page,
            'offset': offset,
        }
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json() if response.content else {}

    def find_status_message(self, where: dict[str, Any], page: int = 1, offset: int = 20) -> dict[str, Any]:
        url = f'{self.base_url}/chat/findStatusMessage/{self.instance.instance_name}'
        payload = {
            'where': where or {},
            'page': page,
            'offset': offset,
        }
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
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
    if isinstance(data, list):
        updated_any = False
        for item in data:
            if not isinstance(item, dict):
                continue
            nested_payload = dict(payload)
            nested_payload['data'] = item
            if process_status_update(nested_payload):
                updated_any = True
        return updated_any
    if not isinstance(data, dict):
        return False
    key_data = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
    external_id_candidates = [
        key_data.get('id'),
        data.get('id'),
        data.get('messageId'),
        payload.get('id'),
    ]
    if isinstance(data.get('message'), dict):
        message_key = data.get('message', {}).get('key', {})
        if isinstance(message_key, dict):
            external_id_candidates.append(message_key.get('id'))
    if isinstance(data.get('update'), dict):
        update_key = data.get('update', {}).get('key', {})
        if isinstance(update_key, dict):
            external_id_candidates.append(update_key.get('id'))
    external_id_candidates = [str(v).strip() for v in external_id_candidates if v]

    status = map_delivery_status(payload)
    message = resolve_message_by_external_candidates(external_id_candidates) if external_id_candidates else None
    if not message:
        # Fallback: atualiza a ultima mensagem enviada da conversa quando webhook vem sem id.
        remote_jid = ''
        if isinstance(key_data, dict):
            remote_jid = str(key_data.get('remoteJid') or key_data.get('participant') or '').strip()
        if not remote_jid and isinstance(data.get('update'), dict) and isinstance(data.get('update', {}).get('key'), dict):
            upd_key = data.get('update', {}).get('key', {})
            remote_jid = str(upd_key.get('remoteJid') or upd_key.get('participant') or '').strip()
        remote_jid = normalize_wa_id(remote_jid) if remote_jid else ''
        if remote_jid:
            conversation = (
                WhatsAppConversation.objects.filter(wa_id=remote_jid).first()
                or WhatsAppConversation.objects.filter(wa_id_alt=remote_jid).first()
            )
            if conversation:
                message = (
                    conversation.mensagens.filter(direcao=WhatsAppMessage.Direction.ENVIADA)
                    .order_by('-criado_em')
                    .first()
                )
    if not message:
        return False

    merged_payload = dict(message.payload or {})
    merged_payload['status_update'] = payload
    message.status = status
    message.payload = merged_payload
    message.save(update_fields=['status', 'payload'])
    return True


def process_message_content_update(payload: dict[str, Any]) -> bool:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    if isinstance(data, list):
        updated_any = False
        for item in data:
            if not isinstance(item, dict):
                continue
            nested_payload = dict(payload)
            nested_payload['data'] = item
            if process_message_content_update(nested_payload):
                updated_any = True
        return updated_any
    if not isinstance(data, dict):
        return False

    key_data = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
    external_id_candidates = [
        key_data.get('id'),
        data.get('id'),
        data.get('messageId'),
        payload.get('id'),
    ]
    external_id_candidates = [str(v).strip() for v in external_id_candidates if v]
    if not external_id_candidates:
        return False

    message_obj = resolve_message_by_external_candidates(external_id_candidates)
    if not message_obj:
        return False

    changed_fields: list[str] = []
    text_before = sanitize_text_content(message_obj.conteudo or '')
    texto = parse_message_text(payload)
    texto = sanitize_text_content(texto)
    media_url, media_kind = parse_message_media(payload)
    raw_message = unwrap_message_content(data.get('message') if isinstance(data.get('message'), dict) else {})
    inferred_kind = infer_message_kind(raw_message, data, payload)

    def _iter_dict_nodes(root: Any):
        stack = [root]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                yield node
                for value in node.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, (dict, list)):
                        stack.append(item)

    def _resolve_media_from_lookup() -> tuple[str, str]:
        external_id = message_obj.external_id or (external_id_candidates[0] if external_id_candidates else '')
        if not external_id:
            return '', ''
        if (inferred_kind or media_kind).lower() not in {'image', 'video', 'audio', 'document', 'sticker'}:
            return '', ''

        instance = message_obj.conversa.instance or get_active_instance()
        if not instance:
            return '', ''

        remote_jid = ''
        if isinstance(data.get('key'), dict):
            remote_jid = str(data.get('key', {}).get('remoteJid') or data.get('key', {}).get('participant') or '').strip()
        if not remote_jid:
            remote_jid = message_obj.conversa.wa_id or message_obj.conversa.wa_id_alt or ''
        remote_jid = normalize_wa_id(remote_jid) if remote_jid else ''

        where_candidates = []
        where_candidates.append({'key': {'id': external_id}})
        where_candidates.append({'id': external_id})
        if remote_jid:
            where_candidates.append({'key': {'id': external_id, 'remoteJid': remote_jid}})
            where_candidates.append({'remoteJid': remote_jid, 'id': external_id})

        client = EvolutionAPIClient(instance=instance)
        responses: list[dict[str, Any]] = []
        for where in where_candidates[:4]:
            try:
                responses.append(client.find_messages(where=where, page=1, offset=20))
            except Exception as exc:
                logger.debug('findMessages falhou para where=%s: %s', where, exc)
            try:
                responses.append(client.find_status_message(where=where, page=1, offset=20))
            except Exception as exc:
                logger.debug('findStatusMessage falhou para where=%s: %s', where, exc)

        for resp in responses:
            for node in _iter_dict_nodes(resp):
                candidate_id = ''
                if isinstance(node.get('key'), dict):
                    candidate_id = str(node.get('key', {}).get('id') or '')
                candidate_id = candidate_id or str(node.get('id') or node.get('messageId') or '')
                if candidate_id and candidate_id != external_id:
                    continue
                candidate_payload = {'data': node}
                found_url, found_kind = parse_message_media(candidate_payload)
                if found_url:
                    return found_url, (found_kind or inferred_kind or media_kind or '').lower()
        return '', ''

    placeholder_values = {
        '',
        '[imagem]',
        '[video]',
        '[audio]',
        '[documento]',
        '[document]',
        '[arquivo]',
        '[figurinha]',
        '[mensagem nao suportada]',
    }
    text_before_norm = text_before.lower()
    should_replace_text = text_before_norm in placeholder_values

    if not media_url:
        looked_url, looked_kind = _resolve_media_from_lookup()
        if looked_url:
            media_url = looked_url
            media_kind = looked_kind or media_kind or inferred_kind
            logger.info('Media recuperada via Evolution lookup para external_id=%s kind=%s', message_obj.external_id or (external_id_candidates[0] if external_id_candidates else ''), media_kind)

    if media_url and media_url != (message_obj.media_url or ''):
        message_obj.media_url = media_url
        changed_fields.append('media_url')

    if texto and (should_replace_text or not text_before):
        message_obj.conteudo = texto
        changed_fields.append('conteudo')
    elif media_url and media_kind and should_replace_text and not texto:
        label = {
            'image': '[IMAGEM]',
            'video': '[VIDEO]',
            'audio': '[AUDIO]',
            'document': '[DOCUMENTO]',
            'sticker': '[FIGURINHA]',
        }.get(media_kind.lower(), '')
        if label:
            message_obj.conteudo = label
            changed_fields.append('conteudo')

    if not changed_fields:
        return False

    merged_payload = dict(message_obj.payload or {})
    merged_payload['message_update'] = payload
    message_obj.payload = merged_payload
    changed_fields.append('payload')
    message_obj.save(update_fields=list(dict.fromkeys(changed_fields)))

    convo = message_obj.conversa
    if convo:
        latest = convo.mensagens.order_by('-criado_em').first()
        if latest and latest.pk == message_obj.pk:
            preview_text = sanitize_text_content(message_obj.conteudo or '')
            if preview_text:
                convo.ultima_mensagem = preview_text[:500]
                convo.ultima_mensagem_em = latest.criado_em
                convo.save(update_fields=['ultima_mensagem', 'ultima_mensagem_em', 'atualizado_em'])
    return True


def process_reaction_update(payload: dict[str, Any]) -> bool:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    if isinstance(data, list):
        updated_any = False
        for item in data:
            if not isinstance(item, dict):
                continue
            nested_payload = dict(payload)
            nested_payload['data'] = item
            if process_reaction_update(nested_payload):
                updated_any = True
        return updated_any
    if not isinstance(data, dict):
        return False

    message = data.get('message', {}) if isinstance(data.get('message'), dict) else {}
    message = unwrap_message_content(message)
    if not isinstance(message, dict):
        return False

    reaction_msg = message.get('reactionMessage')
    if not isinstance(reaction_msg, dict):
        return False

    target_key = reaction_msg.get('key', {}) if isinstance(reaction_msg.get('key'), dict) else {}
    target_candidates = [
        target_key.get('id'),
        data.get('messageId'),
        data.get('id'),
        payload.get('id'),
    ]
    target_candidates = [str(v).strip() for v in target_candidates if v]
    if not target_candidates:
        return False

    target_message = resolve_message_by_external_candidates(target_candidates)
    if not target_message:
        return False

    reaction_emoji = sanitize_text_content(
        reaction_msg.get('text')
        or reaction_msg.get('reaction')
        or data.get('reaction')
        or ''
    )

    actor_key = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
    actor_id = str(actor_key.get('participant') or actor_key.get('remoteJid') or 'unknown').strip() or 'unknown'
    actor_from_me = bool(actor_key.get('fromMe'))

    merged_payload = dict(target_message.payload or {})
    reactions_map = merged_payload.get('reactions_map')
    if not isinstance(reactions_map, dict):
        reactions_map = {}

    if reaction_emoji:
        reactions_map[actor_id] = {
            'emoji': reaction_emoji,
            'from_me': actor_from_me,
            'at': timezone.now().isoformat(),
        }
    else:
        reactions_map.pop(actor_id, None)

    merged_payload['reactions_map'] = reactions_map
    merged_payload['reactions'] = list(reactions_map.values())
    if reaction_emoji:
        merged_payload['last_reaction'] = {
            'emoji': reaction_emoji,
            'from_me': actor_from_me,
            'actor': actor_id,
            'at': timezone.now().isoformat(),
        }
    else:
        merged_payload['last_reaction'] = {}
    merged_payload['reaction_update'] = payload

    target_message.payload = merged_payload
    target_message.save(update_fields=['payload'])
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
    from_me = resolve_from_me(payload, data, key_data, self_jids)

    labels = extract_labels(payload, data if isinstance(data, dict) else {})
    avatar_url = resolve_avatar_url(payload, data if isinstance(data, dict) else {})
    contact_name = resolve_contact_name(payload, data if isinstance(data, dict) else {}).strip()
    if not labels and not avatar_url and not contact_name:
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

    update_fields = ['metadata', 'atualizado_em']
    if labels:
        conversation.etiquetas = labels
        update_fields.append('etiquetas')
    if avatar_url and avatar_url != (conversation.avatar_url or ''):
        conversation.avatar_url = avatar_url
        update_fields.append('avatar_url')
    if contact_name and contact_name != (conversation.nome_contato or ''):
        conversation.nome_contato = contact_name
        update_fields.append('nome_contato')
    merged_meta = dict(conversation.metadata or {})
    event_name_norm = re.sub(r'[^A-Z0-9]+', '_', str(payload.get('event') or '').upper()).strip('_')
    meta_key = 'contacts_update' if event_name_norm == 'CONTACTS_UPDATE' else 'labels_update'
    merged_meta[meta_key] = payload
    conversation.metadata = merged_meta
    conversation.save(update_fields=update_fields)
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
    if isinstance(data, list):
        updated_any = False
        for item in data:
            if not isinstance(item, dict):
                continue
            nested_payload = dict(payload)
            nested_payload['data'] = item
            if process_presence_update(nested_payload, instance=instance):
                updated_any = True
        return updated_any
    if not isinstance(data, dict):
        return False

    self_jids = _extract_self_jids(payload, data, instance=instance)
    updates: list[tuple[str, str]] = []

    presences = data.get('presences')
    if not presences:
        presences = data.get('presence')
    if not presences and isinstance(data.get('data'), (dict, list)):
        presences = data.get('data')
    if isinstance(presences, dict):
        for jid_key, presence_info in presences.items():
            state = ''
            if isinstance(presence_info, dict):
                state = _normalize_presence_state(
                    presence_info.get('lastKnownPresence')
                    or presence_info.get('presence')
                    or presence_info.get('state')
                    or presence_info.get('status')
                    or presence_info.get('type')
                )
            else:
                state = _normalize_presence_state(presence_info)
            updates.append((normalize_wa_id(str(jid_key or '')), state))
    elif isinstance(presences, list):
        for item in presences:
            if not isinstance(item, dict):
                continue
            jid = normalize_wa_id(
                str(
                    item.get('id')
                    or item.get('jid')
                    or item.get('remoteJid')
                    or item.get('participant')
                    or item.get('from')
                    or ''
                )
            )
            state = _normalize_presence_state(
                item.get('lastKnownPresence')
                or item.get('presence')
                or item.get('state')
                or item.get('status')
                or item.get('type')
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
        content_updated = process_message_content_update(payload)
        status_updated = process_status_update(payload)
        reaction_updated = process_reaction_update(payload)
        if content_updated:
            logger.info('Webhook de update de conteudo processado para mensagem existente.')
        if status_updated:
            logger.info('Webhook de status processado para mensagem existente.')
        if reaction_updated:
            logger.info('Webhook de reacao processado para mensagem existente.')
        # Eventos de update/status nao devem criar conversa/mensagem nova
        return

    data = payload.get('data', payload)
    if not isinstance(data, dict):
        return

    key_data = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
    jid_candidates = extract_jid_candidates(payload, data, key_data)

    self_jids = _extract_self_jids(payload, data, instance=instance)
    from_me = resolve_from_me(payload, data, key_data, self_jids)
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
    raw_message = unwrap_message_content(data.get('message') if isinstance(data.get('message'), dict) else {})
    if not texto and not media_url:
        # Evita criar bolha vazia (apenas horario) quando webhook nao traz conteudo real.
        if isinstance(raw_message, dict) and raw_message:
            inferred_kind = infer_message_kind(raw_message, data, payload)
            if inferred_kind in {'image', 'video', 'audio', 'document', 'sticker'}:
                media_kind = media_kind or inferred_kind
                label = {
                    'image': 'IMAGEM',
                    'video': 'VIDEO',
                    'audio': 'AUDIO',
                    'document': 'DOCUMENTO',
                    'sticker': 'FIGURINHA',
                }.get(inferred_kind, inferred_kind.upper())
                texto = f'[{label}]'
            elif inferred_kind in {'reaction', 'protocol', 'key_distribution', 'poll_update'}:
                if inferred_kind == 'reaction':
                    process_reaction_update(payload)
                return
            else:
                texto = '[Mensagem nao suportada]'
        if not texto:
            return
    if not texto and media_kind in {'image', 'video', 'audio', 'sticker'}:
        label = {'image': 'IMAGEM', 'video': 'VIDEO', 'audio': 'AUDIO', 'sticker': 'FIGURINHA'}.get(media_kind, media_kind.upper())
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

    message_created = False
    if ext_id:
        _, message_created = WhatsAppMessage.objects.update_or_create(external_id=ext_id, defaults=defaults)
    else:
        WhatsAppMessage.objects.create(**defaults)
        message_created = True

    if direction == WhatsAppMessage.Direction.RECEBIDA and message_created:
        WhatsAppConversation.objects.filter(pk=conversation.pk).update(nao_lidas=F('nao_lidas') + 1)

    logger.info('Webhook WhatsApp processado: %s', conversation.wa_id)
