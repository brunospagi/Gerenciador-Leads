from __future__ import annotations

import logging
import re
import json
import base64
import binascii
import mimetypes
import uuid
import socket
import ipaddress
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from html import unescape

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
URL_REGEX = re.compile(r'https?://[^\s<>"\']+', flags=re.IGNORECASE)


def _console_log(message: str, level: str = 'INFO') -> None:
    text = f'[WA-MEDIA][{level}] {message}'
    try:
        print(text, flush=True)
    except Exception:
        pass
    log_level = str(level or 'INFO').upper()
    if log_level == 'ERROR':
        logger.error(message)
    elif log_level == 'WARN':
        logger.warning(message)
    elif log_level == 'DEBUG':
        logger.debug(message)
    else:
        logger.info(message)


def sanitize_text_content(value: str) -> str:
    text = str(value or '')
    # Remove caracteres invisiveis que podem gerar bolhas "vazias"
    text = re.sub(r'[\u200b\u200c\u200d\ufeff\u200e\u200f]', '', text)
    return text.strip()


def fit_external_id(value: Any, max_len: int = 150) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    if len(raw) <= max_len:
        return raw
    # Mantem o final do ID para continuar compatível com matching por sufixo.
    return raw[-max_len:]


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
        data.get('profilePic'),
        data.get('profilePicUrlHd'),
        data.get('profilePictureUrl'),
        data.get('profilePicture'),
        data.get('pictureUrl'),
        data.get('imgUrl'),
        data.get('imageUrl'),
        data.get('picture'),
        data.get('avatarUrl'),
        contact_data.get('profilePicUrl'),
        contact_data.get('profilePic'),
        contact_data.get('profilePicUrlHd'),
        contact_data.get('profilePictureUrl'),
        contact_data.get('profilePicture'),
        contact_data.get('picture'),
        contact_data.get('avatarUrl'),
        contact_data.get('imgUrl'),
        contact_data.get('imageUrl'),
        instance_contact.get('profilePicUrl'),
        instance_contact.get('profilePic'),
        instance_contact.get('profilePicUrlHd'),
        instance_contact.get('profilePictureUrl'),
        instance_contact.get('imgUrl'),
        payload.get('profilePicUrl'),
        payload.get('profilePic'),
        payload.get('profilePicUrlHd'),
        payload.get('profilePictureUrl'),
        payload.get('profilePicture'),
        payload.get('pictureUrl'),
        payload.get('imgUrl'),
        payload.get('imageUrl'),
        payload.get('avatarUrl'),
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def extract_jid_candidates(payload: dict[str, Any], data: dict[str, Any], key_data: dict[str, Any]) -> list[str]:
    contact_data = data.get('contact') if isinstance(data.get('contact'), dict) else {}
    instance_data = data.get('instance') if isinstance(data.get('instance'), dict) else {}
    candidates = [
        key_data.get('remoteJid'),
        key_data.get('remoteJidAlt'),
        key_data.get('participant'),
        key_data.get('participantAlt'),
        key_data.get('jid'),
        key_data.get('id'),
        data.get('remoteJid'),
        data.get('remoteJidAlt'),
        data.get('jid'),
        data.get('id'),
        data.get('wa_id'),
        data.get('waId'),
        data.get('number'),
        data.get('phone'),
        data.get('phoneNumber'),
        data.get('from'),
        data.get('sender'),
        data.get('participant'),
        contact_data.get('remoteJid'),
        contact_data.get('jid'),
        contact_data.get('id'),
        contact_data.get('wa_id'),
        contact_data.get('waId'),
        contact_data.get('number'),
        contact_data.get('phone'),
        contact_data.get('phoneNumber'),
        instance_data.get('remoteJid'),
        instance_data.get('jid'),
        instance_data.get('id'),
        payload.get('remoteJid'),
        payload.get('remoteJidAlt'),
        payload.get('jid'),
        payload.get('id'),
        payload.get('number'),
        payload.get('phone'),
        payload.get('phoneNumber'),
        payload.get('from'),
        payload.get('sender'),
    ]
    result = []
    for value in candidates:
        if isinstance(value, str) and value.strip():
            normalized = normalize_wa_id(value.strip())
            is_supported_jid = bool(
                re.match(r'^\d+@s\.whatsapp\.net$', normalized or '')
                or (normalized or '').endswith('@lid')
                or (normalized or '').endswith('@g.us')
            )
            if normalized and is_supported_jid and normalized not in result:
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
    if isinstance(raw_labels, dict) and any(k in raw_labels for k in ('labels', 'tags', 'tag', 'items', 'data', 'result', 'results')):
        for nested_key in ('labels', 'tags', 'tag', 'items', 'data', 'result', 'results'):
            nested_value = raw_labels.get(nested_key)
            parsed_nested = normalize_labels(nested_value)
            for item in parsed_nested:
                if item and item not in labels:
                    labels.append(item)
        return labels
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
                    or item.get('value')
                    or item.get('text')
                    or item.get('id')
                )
                if value:
                    labels.append(str(value).strip())
    elif isinstance(raw_labels, dict):
        value = (
            raw_labels.get('name')
            or raw_labels.get('label')
            or raw_labels.get('title')
            or raw_labels.get('value')
            or raw_labels.get('text')
            or raw_labels.get('id')
        )
        if value:
            labels.append(str(value).strip())
        else:
            for dict_value in raw_labels.values():
                parsed_nested = normalize_labels(dict_value)
                for item in parsed_nested:
                    if item and item not in labels:
                        labels.append(item)
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
        data.get('labelIds'),
        data.get('labelNames'),
        data.get('labelsAssociation'),
        data.get('labelAssociation'),
        data.get('associations'),
        data.get('association'),
        payload.get('labels'),
        payload.get('label'),
        payload.get('tag'),
        payload.get('tags'),
        payload.get('labelIds'),
        payload.get('labelNames'),
        payload.get('labelsAssociation'),
        payload.get('labelAssociation'),
        payload.get('associations'),
        payload.get('association'),
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

    fallback_text = sanitize_text_content(data.get('text') or data.get('body') or '')
    # Alguns providers mandam apenas a URL da midia em text/body no update.
    # Evita renderizar isso como texto comum; o parse de midia deve assumir.
    low = fallback_text.lower()
    if low.startswith('http://') or low.startswith('https://') or low.startswith('/o1/v/') or low.startswith('/v/'):
        return ''
    return fallback_text


def _sanitize_link_url(raw_value: str) -> str:
    raw = str(raw_value or '').strip()
    if not raw:
        return ''
    cleaned = raw.rstrip(').,;!?\'"')
    low = cleaned.lower()
    if not (low.startswith('http://') or low.startswith('https://')):
        return ''
    if any(token in low for token in ['mmg.whatsapp.net', 'lookaside.fbsbx.com', 'cdn.whatsapp.net']):
        return ''
    return cleaned


def _extract_first_http_url(text: str) -> str:
    raw = str(text or '')
    if not raw:
        return ''
    match = URL_REGEX.search(raw)
    if not match:
        return ''
    return _sanitize_link_url(match.group(0))


def _extract_html_meta_content(html: str, key: str, attr: str = 'property') -> str:
    if not html:
        return ''
    pattern = rf'<meta[^>]+{attr}\s*=\s*["\']{re.escape(key)}["\'][^>]*content\s*=\s*["\']([^"\']+)["\']'
    match = re.search(pattern, html, flags=re.IGNORECASE)
    if match:
        return unescape((match.group(1) or '').strip())
    # Alguns sites invertem a ordem dos atributos
    pattern_alt = rf'<meta[^>]+content\s*=\s*["\']([^"\']+)["\'][^>]*{attr}\s*=\s*["\']{re.escape(key)}["\']'
    match_alt = re.search(pattern_alt, html, flags=re.IGNORECASE)
    if match_alt:
        return unescape((match_alt.group(1) or '').strip())
    return ''


def _extract_html_title(html: str) -> str:
    if not html:
        return ''
    match = re.search(r'<title[^>]*>(.*?)</title>', html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ''
    text = re.sub(r'\s+', ' ', match.group(1) or '').strip()
    return unescape(text)


def _is_public_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in {'http', 'https'}:
        return False
    host = (parsed.hostname or '').strip()
    if not host:
        return False
    blocked_hosts = {'localhost', '127.0.0.1', '::1'}
    if host.lower() in blocked_hosts:
        return False
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == 'https' else 80))
    except Exception:
        return False
    for info in infos:
        sockaddr = info[4]
        ip_raw = sockaddr[0] if isinstance(sockaddr, tuple) and sockaddr else ''
        try:
            ip = ipaddress.ip_address(ip_raw)
        except Exception:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return True


def _fetch_link_metadata(url: str) -> dict[str, str]:
    safe_url = _sanitize_link_url(url)
    if not safe_url or not _is_public_http_url(safe_url):
        return {}
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        resp = requests.get(safe_url, timeout=4, headers=headers, allow_redirects=True)
        if not resp.ok:
            return {}
        content_type = str(resp.headers.get('Content-Type') or '').lower()
        if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
            return {}
        html = resp.text or ''
    except Exception:
        return {}

    title = (
        _extract_html_meta_content(html, 'og:title')
        or _extract_html_meta_content(html, 'twitter:title', attr='name')
        or _extract_html_title(html)
    )
    description = (
        _extract_html_meta_content(html, 'og:description')
        or _extract_html_meta_content(html, 'description', attr='name')
        or _extract_html_meta_content(html, 'twitter:description', attr='name')
    )
    image = (
        _extract_html_meta_content(html, 'og:image')
        or _extract_html_meta_content(html, 'twitter:image', attr='name')
    )
    site_name = _extract_html_meta_content(html, 'og:site_name') or (urlparse(safe_url).netloc or '')

    metadata = {
        'url': safe_url,
        'title': str(title or '').strip()[:180],
        'description': str(description or '').strip()[:360],
        'image': str(image or '').strip()[:1200],
        'site_name': str(site_name or '').strip()[:120],
    }
    return {k: v for k, v in metadata.items() if v}


def _enrich_link_preview(preview: dict[str, str]) -> dict[str, str]:
    current = dict(preview or {})
    url = _sanitize_link_url(current.get('url') or '')
    if not url:
        return current
    needs_enrich = not current.get('title') or not current.get('description') or not current.get('image')
    if not needs_enrich:
        return current
    fetched = _fetch_link_metadata(url)
    if not fetched:
        return current
    merged = {
        'url': fetched.get('url') or url,
        'title': current.get('title') or fetched.get('title') or '',
        'description': current.get('description') or fetched.get('description') or '',
        'image': current.get('image') or fetched.get('image') or '',
        'site_name': current.get('site_name') or fetched.get('site_name') or '',
    }
    return {k: str(v).strip() for k, v in merged.items() if str(v or '').strip()}


def extract_link_preview(payload: dict[str, Any], texto: str = '') -> dict[str, str]:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    message = data.get('message', {}) if isinstance(data, dict) else {}
    message = unwrap_message_content(message)
    if not isinstance(message, dict):
        message = {}

    ext = message.get('extendedTextMessage') if isinstance(message.get('extendedTextMessage'), dict) else {}
    context_info = ext.get('contextInfo') if isinstance(ext.get('contextInfo'), dict) else {}
    external_ad = context_info.get('externalAdReply') if isinstance(context_info.get('externalAdReply'), dict) else {}
    search_space = {
        'payload': payload,
        'data': data,
        'message': message,
        'extended': ext,
        'context_info': context_info,
        'external_ad_reply': external_ad,
    }

    def _pick(*keys: str) -> str:
        normalized = {str(k or '').strip().lower() for k in keys if k}
        return _find_nested_value(search_space, normalized)

    url = (
        _sanitize_link_url(_pick('canonicalurl', 'canonical_url'))
        or _sanitize_link_url(_pick('sourceurl', 'source_url'))
        or _sanitize_link_url(_pick('matchedtext', 'matched_text'))
        or _sanitize_link_url(_pick('link', 'url'))
        or _extract_first_http_url(texto)
    )
    if not url:
        return {}

    title = _pick('title')
    description = _pick('description', 'body')
    image = _pick('thumbnailurl', 'thumbnail_url', 'imageurl', 'image_url')
    site_name = _pick('sitename', 'site_name', 'source')

    if not site_name:
        site_name = urlparse(url).netloc

    preview = {
        'url': url[:1200],
        'title': str(title or '').strip()[:180],
        'description': str(description or '').strip()[:360],
        'image': str(image or '').strip()[:1200],
        'site_name': str(site_name or '').strip()[:120],
    }
    compact = {k: v for k, v in preview.items() if v}
    return _enrich_link_preview(compact)


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
        parsed = urlparse(candidate) if candidate.startswith('http://') or candidate.startswith('https://') else None
        check_value = (parsed.path or '') if parsed else candidate
        host = (parsed.hostname or '').lower() if parsed else ''
        return (
            bool(re.search(r'(?:^|[/?])[^/?#]+\.enc(?:$|[?#])', candidate))
            or check_value.startswith('/v/t62')
            or check_value.startswith('/o1/v/t24')
            or check_value.startswith('/v/t24')
            or check_value.startswith('/o1/v/t62')
            or (host.endswith('mmg.whatsapp.net') and ('/o1/v/t24/' in check_value or '/v/t24/' in check_value))
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
            # Mantem URLs locais do proprio sistema (/media, /static, etc).
            # Prefixa dominio do WhatsApp apenas para caminhos tipicos de midia remota.
            if re.match(r'^/(?:o\d+/)?v/', candidate, flags=re.IGNORECASE):
                return f'https://mmg.whatsapp.net{candidate}'
            return candidate
        return candidate

    def _guess_mime_from_bytes(content: bytes) -> str:
        data_bytes = bytes(content or b'')
        if not data_bytes:
            return ''
        head = data_bytes[:32]
        if head.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        if head.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        if head.startswith(b'GIF87a') or head.startswith(b'GIF89a'):
            return 'image/gif'
        if head.startswith(b'RIFF') and b'WEBP' in data_bytes[:16]:
            return 'image/webp'
        if head.startswith(b'%PDF'):
            return 'application/pdf'
        if head.startswith(b'OggS'):
            return 'audio/ogg'
        if head[:4] == b'fLaC':
            return 'audio/flac'
        if len(data_bytes) > 12 and data_bytes[4:8] == b'ftyp':
            # mp4/m4a/mov
            brand = data_bytes[8:12]
            if brand in {b'M4A ', b'isom', b'mp42', b'qt  '}:
                return 'video/mp4'
        if head.startswith(b'\x1aE\xdf\xa3'):
            return 'video/webm'
        if head[:3] == b'ID3' or (len(head) > 2 and (head[0] == 0xFF and (head[1] & 0xE0) == 0xE0)):
            return 'audio/mpeg'
        if head.startswith(b'PK\x03\x04'):
            return 'application/zip'
        return ''

    def _mime_matches_kind(mime_value: str, media_kind: str) -> bool:
        mime = str(mime_value or '').lower()
        kind = str(media_kind or '').lower()
        if not kind or kind == 'document':
            return True
        if kind == 'sticker':
            return mime.startswith('image/')
        if kind == 'image':
            return mime.startswith('image/')
        if kind == 'video':
            return mime.startswith('video/')
        if kind == 'audio':
            return mime.startswith('audio/')
        return True

    def _persist_media_from_url(media_url: str, mime_value: str, media_kind: str) -> str:
        normalized = _normalize_public_media_url(media_url)
        if not normalized:
            return ''
        lower = normalized.lower()
        if lower.startswith('data:'):
            return normalized
        if not (lower.startswith('http://') or lower.startswith('https://')):
            return ''

        mime = str(mime_value or '').strip().lower()
        kind = str(media_kind or '').strip().lower() or 'document'

        # Somente tenta persistir links temporarios/externos; para URLs internas locais, mantem como estao.
        # Inclui URLs pre-assinadas S3 (X-Amz-*) para evitar expiracao no chat.
        is_whatsapp_cdn = any(token in lower for token in ['mmg.whatsapp.net', 'lookaside.fbsbx.com', 'cdn.whatsapp.net'])
        is_presigned_s3 = (
            ('x-amz-signature=' in lower)
            or ('x-amz-credential=' in lower)
            or ('x-amz-algorithm=' in lower)
            or ('x-amz-date=' in lower)
        )
        is_evolution_s3_path = '/evolution/evolution-api/' in lower
        persist_hint = is_whatsapp_cdn or is_presigned_s3 or is_evolution_s3_path
        if not persist_hint:
            return ''

        # Se ja for URL estavel do nosso bucket principal sem assinatura, nao precisa copiar de novo.
        if ('s3.spagisistemas.com.br' in lower) and ('x-amz-signature=' not in lower):
            return normalized

        def _download_with_headers(url_value: str) -> requests.Response | None:
            browser_headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                ),
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://web.whatsapp.com/',
                'Origin': 'https://web.whatsapp.com',
            }
            try:
                response = requests.get(url_value, timeout=60, headers=browser_headers, allow_redirects=True)
                if response.ok and (response.content or b''):
                    return response
            except Exception:
                pass
            try:
                response = requests.get(url_value, timeout=60, allow_redirects=True)
                if response.ok and (response.content or b''):
                    return response
            except Exception:
                pass
            return None

        resp = _download_with_headers(normalized)
        if not resp:
            _console_log(f'Falha ao baixar media remota para persistencia: url={normalized}', 'DEBUG')
            return ''
        final_response_url = str(getattr(resp, 'url', '') or '').strip()
        if _is_encrypted_media_ref(final_response_url):
            _console_log(f'URL final da midia ainda aponta para referencia criptografada: {final_response_url}', 'WARN')
            return ''

        content = resp.content or b''
        if not content:
            return ''

        content_type = str(resp.headers.get('Content-Type') or '').split(';', 1)[0].strip().lower()
        if content_type.startswith('text/') or content_type in {'application/json', 'application/xml'}:
            logger.debug('Conteudo remoto nao e midia valida: content_type=%s url=%s', content_type, normalized)
            return ''

        detected_mime = _guess_mime_from_bytes(content)
        final_mime = detected_mime or content_type or mime or 'application/octet-stream'
        # Para midias renderizaveis, nao confiar apenas no header remoto.
        # Se os bytes nao forem reconhecidos, pode ser .enc/criptografado.
        if kind in {'image', 'video', 'audio', 'sticker'} and not detected_mime:
            _console_log(
                f'Midia remota sem assinatura reconhecivel nos bytes (possivel .enc): kind={kind} url={normalized} content_type={content_type} - usando fallback por base64.',
                'INFO',
            )
            return ''
        if not _mime_matches_kind(final_mime, kind):
            logger.debug(
                'Mime baixado nao confere com tipo esperado: expected_kind=%s final_mime=%s url=%s',
                kind,
                final_mime,
                normalized,
            )
            return ''

        extension = mimetypes.guess_extension(final_mime) or ''
        if not extension:
            extension = {
                'image': '.jpg',
                'video': '.mp4',
                'audio': '.ogg',
                'sticker': '.webp',
                'document': '.bin',
            }.get(kind, '.bin')

        unique_name = f'{uuid.uuid4().hex}{extension}'
        storage_path = f'whatsapp/webhook/{timezone.now().strftime("%Y/%m")}/{unique_name}'
        file_obj = ContentFile(content, name=unique_name)
        try:
            storage = PublicMediaStorage()
            saved_path = storage.save(storage_path, file_obj)
            logger.info('WhatsApp media URL persistida no MinIO: kind=%s path=%s', kind, saved_path)
            return storage.url(saved_path)
        except Exception as exc:
            logger.warning('Falha ao persistir media URL no MinIO, tentando storage padrao: %s', exc)
            try:
                fallback_file_obj = ContentFile(content, name=unique_name)
                saved_path = default_storage.save(storage_path, fallback_file_obj)
                logger.info('WhatsApp media URL persistida no storage padrao: kind=%s path=%s', kind, saved_path)
                return default_storage.url(saved_path)
            except Exception as fallback_exc:
                logger.warning('Falha ao persistir media URL no storage padrao: %s', fallback_exc)
                return ''

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

        detected_mime = _guess_mime_from_bytes(decoded)
        final_mime = detected_mime or mime.split(';', 1)[0].strip().lower() or 'application/octet-stream'
        if media_kind in {'image', 'video', 'audio', 'sticker'} and not detected_mime:
            _console_log(
                f'Base64 de midia sem assinatura reconhecivel (possivel conteudo criptografado): kind={media_kind} mime_hint={mime}',
                'WARN',
            )
            return ''
        if not _mime_matches_kind(final_mime, media_kind):
            return ''

        extension = mimetypes.guess_extension(final_mime) or ''
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
                return f'data:{final_mime};base64,{source_data}'

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
                or message.get('base64')
                or message.get('mediaBase64')
                or message.get('fileBase64')
                or data.get('base64')
                or data.get('mediaBase64')
                or data.get('fileBase64')
                or payload.get('base64')
                or payload.get('mediaBase64')
                or payload.get('fileBase64')
                or ''
            )
            if media_url and not _is_encrypted_media_ref(media_url):
                persisted_remote = _persist_media_from_url(media_url, str(mime or 'application/octet-stream'), media_kind)
                if persisted_remote:
                    return persisted_remote, media_kind
                if any(token in media_url.lower() for token in ['mmg.whatsapp.net', 'lookaside.fbsbx.com', 'cdn.whatsapp.net']):
                    media_url = ''
                if media_url:
                    return media_url, media_kind

            persisted_url = _media_from_base64(str(mime or 'application/octet-stream'), base64_data, media_kind)
            if persisted_url:
                return persisted_url, media_kind

            # Fallback final: directPath quase sempre eh referencia criptografada.
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
            inferred_kind = 'document'
            if 'sticker' in msg_type:
                inferred_kind = 'sticker'
            elif mime.startswith('image/') or 'image' in msg_type:
                inferred_kind = 'image'
            elif mime.startswith('video/') or 'video' in msg_type:
                inferred_kind = 'video'
            elif mime.startswith('audio/') or 'audio' in msg_type or 'ptt' in msg_type:
                inferred_kind = 'audio'
            persisted_remote = _persist_media_from_url(generic_url, mime, inferred_kind)
            final_url = persisted_remote
            if not final_url and not any(token in generic_url.lower() for token in ['mmg.whatsapp.net', 'lookaside.fbsbx.com', 'cdn.whatsapp.net']):
                final_url = generic_url
            if not final_url:
                return '', inferred_kind
            if 'sticker' in msg_type:
                return final_url, 'sticker'
            if mime.startswith('image/') or 'image' in msg_type:
                return final_url, 'image'
            if mime.startswith('video/') or 'video' in msg_type:
                return final_url, 'video'
            if mime.startswith('audio/') or 'audio' in msg_type or 'ptt' in msg_type:
                return final_url, 'audio'
            return final_url, 'document'

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
            persisted_remote = _persist_media_from_url(candidate_url, candidate_mime, candidate_kind)
            if persisted_remote:
                return persisted_remote, candidate_kind
            if not any(token in candidate_url.lower() for token in ['mmg.whatsapp.net', 'lookaside.fbsbx.com', 'cdn.whatsapp.net']):
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
            persisted_remote = _persist_media_from_url(candidate_url, candidate_mime, candidate_kind)
            if persisted_remote:
                return persisted_remote, candidate_kind
            if not any(token in candidate_url.lower() for token in ['mmg.whatsapp.net', 'lookaside.fbsbx.com', 'cdn.whatsapp.net']):
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


def fallback_contact_name_by_wa_id(name: str, wa_id: str) -> str:
    cleaned_name = str(name or '').strip()
    if cleaned_name:
        return cleaned_name
    jid = str(wa_id or '').strip().lower()
    if not jid:
        return ''
    if '@s.whatsapp.net' not in jid:
        return ''
    local = jid.split('@', 1)[0]
    digits = re.sub(r'\D', '', local)
    return digits or local


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
    source = _find_nested_value(search_space, {'source', 'utm_source'}) or ''
    fbclid = _find_nested_value(search_space, {'fbclid'}) or ''
    campaign_id = _find_nested_value(search_space, {'campaignid', 'campaign_id'}) or ''
    adset_id = _find_nested_value(search_space, {'adsetid', 'adset_id'}) or ''
    ad_id = _find_nested_value(search_space, {'adid', 'ad_id'}) or ''
    source_id = _find_nested_value(search_space, {'sourceid', 'source_id'}) or ''
    ref = _find_nested_value(search_space, {'ref'}) or ''
    ad_link = _find_nested_value(search_space, {'adlink', 'ad_link', 'sourceurl', 'source_url'}) or ''
    conversion_source = _find_nested_value(search_space, {'conversionsource', 'conversion_source'}) or ''
    conversion_data = _find_nested_value(search_space, {'conversiondata', 'conversion_data'}) or ''

    def _normalize_if_fb_link(value: str) -> str:
        raw = str(value or '').strip()
        if not raw:
            return ''
        low = raw.lower()
        fb_tokens = ['facebook.com', 'instagram.com', 'fbclid=', 'utm_source=facebook', 'ctwa', 'click_to_whatsapp']
        return raw if any(token in low for token in fb_tokens) else ''

    ad_link = _normalize_if_fb_link(ad_link)
    if not source and conversion_source:
        source = conversion_source

    metadata = {
        'source': source,
        'fbclid': fbclid,
        'campaign_id': campaign_id,
        'adset_id': adset_id,
        'ad_id': ad_id,
        'source_id': source_id,
        'ref': ref,
        'ad_link': ad_link,
        'conversion_source': conversion_source,
    }
    # Evita salvar payload gigante no metadata/aviso.
    if conversion_data:
        metadata['conversion_data'] = f'{conversion_data[:120]}...'
    metadata = {k: v for k, v in metadata.items() if v}

    lower_source = (source or '').strip().lower()
    lower_ref = (ref or '').strip().lower()
    lower_conversion_source = (conversion_source or '').strip().lower()
    source_looks_facebook = any(
        token in lower_source for token in ['facebook', 'meta', 'instagram', 'ctwa', 'click_to_whatsapp']
    ) or any(token in lower_ref for token in ['facebook', 'meta', 'instagram', 'ctwa', 'click_to_whatsapp'])
    conversion_source_looks_facebook = any(
        token in lower_conversion_source for token in ['facebook', 'meta', 'instagram', 'fb_ads', 'ads', 'ctwa']
    )
    has_fbclid = bool(fbclid)
    has_ad_ids = bool(campaign_id or adset_id or ad_id or source_id)
    has_ctwa_hint = bool(_find_nested_value(search_space, {'ctwa', 'click_to_whatsapp', 'externaladreply'}))
    has_conversion_hint = bool(conversion_source or conversion_data)

    # Evita falso positivo (ex.: source=android ou URL de midia comum).
    matched = (
        has_fbclid
        or source_looks_facebook
        or conversion_source_looks_facebook
        or has_ctwa_hint
        or (has_ad_ids and (has_indicator or source_looks_facebook or conversion_source_looks_facebook))
        or (has_conversion_hint and conversion_source_looks_facebook)
    )
    return matched, metadata


def _build_ads_system_message(ads_metadata: dict[str, str]) -> str:
    source = ads_metadata.get('source') or ''
    conversion_source = ads_metadata.get('conversion_source') or ''
    if conversion_source and source.strip().lower() in {'', 'android', 'ios', 'web', 'desktop'}:
        source = conversion_source
    source = source or 'Facebook Ads'
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

    def _post_with_payload_variants(
        self,
        endpoint: str,
        payload_variants: list[dict[str, Any]],
        timeout: int = 30,
    ) -> dict[str, Any]:
        def _is_payload_error(data: Any) -> bool:
            if not isinstance(data, dict):
                return False
            status = data.get('status')
            status_code = data.get('statusCode')
            for val in (status, status_code):
                try:
                    if int(val) >= 400:
                        return True
                except (TypeError, ValueError):
                    pass
            error_value = data.get('error')
            if isinstance(error_value, bool) and error_value:
                return True
            if isinstance(error_value, str) and error_value.strip():
                return True
            message_value = data.get('message')
            if isinstance(message_value, dict):
                nested_error = message_value.get('error')
                if isinstance(nested_error, bool) and nested_error:
                    return True
                if isinstance(nested_error, str) and nested_error.strip():
                    return True
            return False

        last_error = None
        for payload in payload_variants:
            try:
                response = requests.post(endpoint, json=payload, headers=self.headers, timeout=timeout)
                response.raise_for_status()
                data = response.json() if response.content else {}
                if _is_payload_error(data):
                    logger.debug('Evolution retornou erro sem HTTP fail. endpoint=%s payload_keys=%s', endpoint, list(payload.keys()))
                    continue
                return data
            except requests.RequestException as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        raise RuntimeError('Nao foi possivel enviar requisicao para Evolution API.')

    def send_text(
        self,
        number: str,
        text: str,
        quoted_key: dict[str, Any] | None = None,
        quoted_text: str = '',
    ) -> dict[str, Any]:
        url = f'{self.base_url}/message/sendText/{self.instance.instance_name}'
        base_payload = {'number': normalize_number(number), 'text': text}
        payload_variants = [base_payload]
        if quoted_key and isinstance(quoted_key, dict):
            q_remote = str(quoted_key.get('remoteJid') or '').strip()
            q_id = str(quoted_key.get('id') or '').strip()
            if q_remote and q_id:
                normalized_key = {
                    'remoteJid': q_remote,
                    'fromMe': bool(quoted_key.get('fromMe')),
                    'id': q_id,
                }
                preview_text = str(quoted_text or '').strip()[:240] or 'Mensagem'
                payload_variants = [
                    {**base_payload, 'quoted': {'key': {'id': q_id}, 'message': {'conversation': preview_text}}},
                    {**base_payload, 'quoted': {'key': normalized_key, 'message': {'conversation': preview_text}}},
                    {**base_payload, 'quoted': {'key': {'id': q_id}}},
                    {**base_payload, 'quoted': normalized_key},
                    {**base_payload, 'quotedMessage': normalized_key},
                    {**base_payload, 'quotedMessageId': q_id},
                    {**base_payload, 'options': {'quoted': normalized_key}},
                ]
        return self._post_with_payload_variants(url, payload_variants, timeout=30)

    def send_media(
        self,
        number: str,
        media_url: str,
        mediatype: str,
        mimetype: str,
        caption: str = '',
        file_name: str = '',
        quoted_key: dict[str, Any] | None = None,
        quoted_text: str = '',
    ) -> dict[str, Any]:
        url = f'{self.base_url}/message/sendMedia/{self.instance.instance_name}'
        base_payload = {
            'number': normalize_number(number),
            'mediatype': mediatype,
            'mimetype': mimetype,
            'caption': caption or '',
            'media': media_url,
        }
        if file_name:
            base_payload['fileName'] = file_name
        payload_variants = [base_payload]
        if quoted_key and isinstance(quoted_key, dict):
            q_remote = str(quoted_key.get('remoteJid') or '').strip()
            q_id = str(quoted_key.get('id') or '').strip()
            if q_remote and q_id:
                normalized_key = {
                    'remoteJid': q_remote,
                    'fromMe': bool(quoted_key.get('fromMe')),
                    'id': q_id,
                }
                preview_text = str(quoted_text or '').strip()[:240] or 'Mensagem'
                payload_variants = [
                    {**base_payload, 'quoted': {'key': {'id': q_id}, 'message': {'conversation': preview_text}}},
                    {**base_payload, 'quoted': {'key': normalized_key, 'message': {'conversation': preview_text}}},
                    {**base_payload, 'quoted': {'key': {'id': q_id}}},
                    {**base_payload, 'quoted': normalized_key},
                    {**base_payload, 'quotedMessage': normalized_key},
                    {**base_payload, 'quotedMessageId': q_id},
                    {**base_payload, 'options': {'quoted': normalized_key}},
                ]
        return self._post_with_payload_variants(url, payload_variants, timeout=60)

    def send_whatsapp_audio(
        self,
        number: str,
        audio_url: str,
        quoted_key: dict[str, Any] | None = None,
        quoted_text: str = '',
    ) -> dict[str, Any]:
        url = f'{self.base_url}/message/sendWhatsAppAudio/{self.instance.instance_name}'
        base_payload = {
            'number': normalize_number(number),
            'audio': audio_url,
        }
        payload_variants = [base_payload]
        if quoted_key and isinstance(quoted_key, dict):
            q_remote = str(quoted_key.get('remoteJid') or '').strip()
            q_id = str(quoted_key.get('id') or '').strip()
            if q_remote and q_id:
                normalized_key = {
                    'remoteJid': q_remote,
                    'fromMe': bool(quoted_key.get('fromMe')),
                    'id': q_id,
                }
                preview_text = str(quoted_text or '').strip()[:240] or 'Mensagem'
                payload_variants = [
                    {**base_payload, 'quoted': {'key': {'id': q_id}, 'message': {'conversation': preview_text}}},
                    {**base_payload, 'quoted': {'key': normalized_key, 'message': {'conversation': preview_text}}},
                    {**base_payload, 'quoted': {'key': {'id': q_id}}},
                    {**base_payload, 'quoted': normalized_key},
                    {**base_payload, 'quotedMessage': normalized_key},
                    {**base_payload, 'quotedMessageId': q_id},
                    {**base_payload, 'options': {'quoted': normalized_key}},
                ]
        return self._post_with_payload_variants(url, payload_variants, timeout=60)

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

    def find_contacts(self, where: dict[str, Any] | None = None, page: int = 1, offset: int = 200) -> dict[str, Any]:
        payload = {
            'where': where or {},
            'page': max(1, int(page or 1)),
            'offset': max(1, int(offset or 200)),
        }
        endpoints = [
            f'{self.base_url}/chat/findContacts/{self.instance.instance_name}',
            f'{self.base_url}/chat/findContact/{self.instance.instance_name}',
            f'{self.base_url}/contacts/find/{self.instance.instance_name}',
        ]
        last_error = None
        for endpoint in endpoints:
            try:
                response = requests.post(endpoint, json=payload, headers=self.headers, timeout=45)
                response.raise_for_status()
                return response.json() if response.content else {}
            except requests.RequestException as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return {}

    def find_chats(self, where: dict[str, Any] | None = None, page: int = 1, offset: int = 200) -> dict[str, Any]:
        payload = {
            'where': where or {},
            'page': max(1, int(page or 1)),
            'offset': max(1, int(offset or 200)),
        }
        endpoints = [
            f'{self.base_url}/chat/findChats/{self.instance.instance_name}',
            f'{self.base_url}/chat/findChat/{self.instance.instance_name}',
        ]
        last_error = None
        for endpoint in endpoints:
            try:
                response = requests.post(endpoint, json=payload, headers=self.headers, timeout=45)
                response.raise_for_status()
                return response.json() if response.content else {}
            except requests.RequestException as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return {}

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

    def get_base64_from_media_message(
        self,
        message_id: str,
        convert_to_mp4: bool = False,
        message_key: dict[str, Any] | None = None,
        message_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f'{self.base_url}/chat/getBase64FromMediaMessage/{self.instance.instance_name}'
        msg_id = str(message_id or '').strip()
        base_payload = {
            'convertToMp4': bool(convert_to_mp4),
        }
        key_payload = dict(message_key or {})
        if msg_id and not key_payload.get('id'):
            key_payload['id'] = msg_id

        payload_variants = []
        raw_message_payload = message_payload if isinstance(message_payload, dict) else {}
        if raw_message_payload:
            payload_variants.extend(
                [
                    {**base_payload, 'message': raw_message_payload},
                    {**base_payload, 'data': raw_message_payload},
                    {**base_payload, **raw_message_payload},
                ]
            )
        if key_payload.get('id'):
            payload_variants.extend(
                [
                    {**base_payload, 'message': {'key': key_payload}},
                    {**base_payload, 'message': {'key': {'id': key_payload.get('id')}}},
                    {**base_payload, 'key': key_payload},
                    {**base_payload, 'key': {'id': key_payload.get('id')}},
                    {**base_payload, 'id': key_payload.get('id')},
                    {**base_payload, 'messageId': key_payload.get('id')},
                ]
            )

        if msg_id:
            payload_variants.extend(
                [
                    {**base_payload, 'message': {'id': msg_id}},
                    {**base_payload, 'message': {'key': {'id': msg_id}}},
                ]
            )

        return self._post_with_payload_variants(url, payload_variants, timeout=60)

    def get_s3_media_url(
        self,
        message_id: str,
        message_key: dict[str, Any] | None = None,
        message_payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        endpoint = f'{self.base_url}/s3/getMediaUrl/{self.instance.instance_name}'
        msg_id = str(message_id or '').strip()
        key_payload = dict(message_key or {})
        if msg_id and not key_payload.get('id'):
            key_payload['id'] = msg_id
        raw_message_payload = message_payload if isinstance(message_payload, dict) else {}
        query_payload = dict(query or {})
        payload_variants: list[dict[str, Any]] = []
        if query_payload:
            payload_variants.append(query_payload)
        if raw_message_payload:
            payload_variants.extend(
                [
                    {'message': raw_message_payload},
                    {'data': raw_message_payload},
                    raw_message_payload,
                ]
            )
        if key_payload.get('id'):
            payload_variants.extend(
                [
                    {'message': {'key': key_payload}},
                    {'message': {'key': {'id': key_payload.get('id')}}},
                    {'key': key_payload},
                    {'id': key_payload.get('id')},
                    {'messageId': key_payload.get('id')},
                ]
            )
        if msg_id:
            payload_variants.extend([{'message': {'id': msg_id}}])
        return self._post_with_payload_variants(endpoint, payload_variants, timeout=60)

    def get_s3_media(
        self,
        message_id: str,
        message_key: dict[str, Any] | None = None,
        message_payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        endpoint = f'{self.base_url}/s3/getMedia/{self.instance.instance_name}'
        msg_id = str(message_id or '').strip()
        key_payload = dict(message_key or {})
        if msg_id and not key_payload.get('id'):
            key_payload['id'] = msg_id
        raw_message_payload = message_payload if isinstance(message_payload, dict) else {}
        query_payload = dict(query or {})
        payload_variants: list[dict[str, Any]] = []
        if query_payload:
            payload_variants.append(query_payload)
        if raw_message_payload:
            payload_variants.extend(
                [
                    {'message': raw_message_payload},
                    {'data': raw_message_payload},
                    raw_message_payload,
                ]
            )
        if key_payload.get('id'):
            payload_variants.extend(
                [
                    {'message': {'key': key_payload}},
                    {'message': {'key': {'id': key_payload.get('id')}}},
                    {'key': key_payload},
                    {'id': key_payload.get('id')},
                    {'messageId': key_payload.get('id')},
                ]
            )
        if msg_id:
            payload_variants.extend([{'message': {'id': msg_id}}])
        return self._post_with_payload_variants(endpoint, payload_variants, timeout=60)


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
        'queued': WhatsAppMessage.Status.PENDENTE,
    }
    raw_candidates = [
        data.get('status'),
        data.get('messageStatus'),
        payload.get('status'),
    ]
    if isinstance(data.get('update'), dict):
        raw_candidates.extend([
            data.get('update', {}).get('status'),
            data.get('update', {}).get('messageStatus'),
        ])
    for candidate in raw_candidates:
        if candidate is None:
            continue
        raw_status_str = str(candidate).strip().lower()
        if not raw_status_str:
            continue
        if raw_status_str in status_map:
            return status_map[raw_status_str]
        # Alguns provedores enviam ACK numerico em formato string no campo "status".
        if raw_status_str in {'-1', '0', '1', '2', '3', '4'}:
            try:
                ack_as_status = int(raw_status_str)
            except (TypeError, ValueError):
                ack_as_status = None
            if ack_as_status == -1:
                return WhatsAppMessage.Status.FALHA
            if ack_as_status == 0:
                return WhatsAppMessage.Status.PENDENTE
            if ack_as_status == 1:
                return WhatsAppMessage.Status.ENVIADA
            if ack_as_status == 2:
                return WhatsAppMessage.Status.ENTREGUE
            if ack_as_status in {3, 4}:
                return WhatsAppMessage.Status.LIDA

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

    return ''


def _status_rank(status: str) -> int:
    normalized = str(status or '').strip().lower()
    if normalized == WhatsAppMessage.Status.PENDENTE:
        return 0
    if normalized == WhatsAppMessage.Status.ENVIADA:
        return 1
    if normalized == WhatsAppMessage.Status.ENTREGUE:
        return 2
    if normalized == WhatsAppMessage.Status.LIDA:
        return 3
    if normalized == WhatsAppMessage.Status.FALHA:
        return -1
    return -2


def merge_delivery_status(current_status: str, incoming_status: str) -> str:
    current = str(current_status or '').strip().lower()
    incoming = str(incoming_status or '').strip().lower()
    if not incoming:
        return current or WhatsAppMessage.Status.PENDENTE
    if not current:
        return incoming

    # Falha deve prevalecer apenas quando ainda nao houve confirmacao superior.
    if incoming == WhatsAppMessage.Status.FALHA:
        if _status_rank(current) >= _status_rank(WhatsAppMessage.Status.ENTREGUE):
            return current
        return incoming
    if current == WhatsAppMessage.Status.FALHA:
        return current

    # Nunca faz downgrade (ex.: read -> sent).
    if _status_rank(incoming) < _status_rank(current):
        return current
    return incoming


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


def _extract_node_message_ids(node: dict[str, Any]) -> list[str]:
    if not isinstance(node, dict):
        return []
    ids: list[str] = []
    candidates = [
        node.get('id'),
        node.get('messageId'),
        node.get('msgId'),
    ]
    key_data = node.get('key', {}) if isinstance(node.get('key'), dict) else {}
    candidates.append(key_data.get('id'))
    update_data = node.get('update', {}) if isinstance(node.get('update'), dict) else {}
    update_key = update_data.get('key', {}) if isinstance(update_data.get('key'), dict) else {}
    candidates.append(update_data.get('id'))
    candidates.append(update_data.get('messageId'))
    candidates.append(update_key.get('id'))
    for raw in candidates:
        value = fit_external_id(raw)
        if value and value not in ids:
            ids.append(value)
    return ids


def _extract_contact_jid_from_node(node: dict[str, Any]) -> str:
    if not isinstance(node, dict):
        return ''
    candidates = [
        node.get('remoteJid'),
        node.get('jid'),
        node.get('wa_id'),
        node.get('waId'),
        node.get('whatsappId'),
        node.get('id'),
    ]
    for raw in candidates:
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if not value:
            continue
        normalized = normalize_wa_id(value)
        if normalized and ('@' in normalized or normalized.isdigit()):
            return normalized
    phone_candidates = [
        node.get('number'),
        node.get('phone'),
        node.get('phoneNumber'),
        node.get('mobile'),
    ]
    for raw in phone_candidates:
        digits = normalize_number(str(raw or ''))
        if digits:
            return f'{digits}@s.whatsapp.net'
    return ''


def _extract_contact_name_from_node(node: dict[str, Any]) -> str:
    if not isinstance(node, dict):
        return ''
    for key in ('pushName', 'name', 'fullName', 'shortName', 'notify'):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def _extract_contact_avatar_from_node(node: dict[str, Any]) -> str:
    if not isinstance(node, dict):
        return ''
    contact_data = node.get('contact') if isinstance(node.get('contact'), dict) else {}
    for key in (
        'profilePicUrl',
        'profilePic',
        'profilePicUrlHd',
        'profilePictureUrl',
        'profilePicture',
        'pictureUrl',
        'imgUrl',
        'imageUrl',
        'avatarUrl',
    ):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        nested_value = contact_data.get(key)
        if isinstance(nested_value, str) and nested_value.strip():
            return nested_value.strip()
    return ''


def _iter_contact_like_nodes(root: Any):
    stack = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            jid = _extract_contact_jid_from_node(node)
            labels = normalize_labels(node.get('labels') or node.get('tags') or node.get('tag'))
            name = _extract_contact_name_from_node(node)
            avatar = _extract_contact_avatar_from_node(node)
            if jid and (labels or name or avatar or jid.endswith('@s.whatsapp.net') or jid.endswith('@lid')):
                yield node
            for value in node.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    stack.append(item)


def reconcile_contact_labels(
    *,
    page_size: int = 200,
    max_pages: int = 8,
    clear_missing: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    instance = get_active_instance()
    stats = {
        'checked': 0,
        'matched': 0,
        'updated': 0,
        'labels_updated': 0,
        'name_updated': 0,
        'avatar_updated': 0,
        'cleared_labels': 0,
        'no_conversation': 0,
        'pages': 0,
        'api_errors': 0,
        'no_instance': 0,
    }
    if not instance:
        stats['no_instance'] = 1
        return stats

    client = EvolutionAPIClient(instance=instance)
    seen_jids: set[str] = set()
    labels_by_jid: dict[str, list[str]] = {}
    now = timezone.now().isoformat()

    def _find_conversation_for_jid(jid: str) -> WhatsAppConversation | None:
        norm = normalize_wa_id(jid)
        if not norm:
            return None
        conversation = (
            WhatsAppConversation.objects.filter(wa_id=norm).first()
            or WhatsAppConversation.objects.filter(wa_id_alt=norm).first()
        )
        if conversation:
            return conversation

        # Fallback por numero para cobrir diferencas entre @lid e @s.whatsapp.net.
        local = norm.split('@', 1)[0]
        digits = normalize_number(local)
        if not digits:
            return None
        conversation = (
            WhatsAppConversation.objects.filter(wa_id__startswith=f'{digits}@').first()
            or WhatsAppConversation.objects.filter(wa_id_alt__startswith=f'{digits}@').first()
        )
        return conversation

    def _upsert_from_node(node: dict[str, Any]) -> None:
        jid = normalize_wa_id(_extract_contact_jid_from_node(node))
        if not jid:
            return
        seen_jids.add(jid)
        labels = normalize_labels(node.get('labels') or node.get('tags') or node.get('tag'))
        labels_by_jid[jid] = labels
        contact_name = fallback_contact_name_by_wa_id(_extract_contact_name_from_node(node), jid)
        avatar_url = _extract_contact_avatar_from_node(node)

        stats['checked'] += 1
        conversation = _find_conversation_for_jid(jid)
        if not conversation:
            stats['no_conversation'] += 1
            return

        stats['matched'] += 1
        changed = False
        update_fields = ['metadata', 'atualizado_em']

        if is_real_number_jid(jid) and conversation.wa_id != jid:
            collision = WhatsAppConversation.objects.filter(wa_id=jid).exclude(pk=conversation.pk).exists()
            if not collision:
                old_wa_id = conversation.wa_id
                conversation.wa_id = jid
                if is_lid_jid(old_wa_id) and not conversation.wa_id_alt:
                    conversation.wa_id_alt = old_wa_id
                update_fields.append('wa_id')
                changed = True
        if is_lid_jid(jid) and jid != conversation.wa_id and jid != (conversation.wa_id_alt or ''):
            conversation.wa_id_alt = jid
            update_fields.append('wa_id_alt')
            changed = True

        if labels and labels != (conversation.etiquetas or []):
            conversation.etiquetas = labels
            update_fields.append('etiquetas')
            stats['labels_updated'] += 1
            changed = True

        if avatar_url and avatar_url != (conversation.avatar_url or ''):
            conversation.avatar_url = avatar_url
            update_fields.append('avatar_url')
            stats['avatar_updated'] += 1
            changed = True

        if contact_name and contact_name != (conversation.nome_contato or ''):
            conversation.nome_contato = contact_name
            update_fields.append('nome_contato')
            stats['name_updated'] += 1
            changed = True

        if not changed:
            return

        if dry_run:
            stats['updated'] += 1
            return

        merged_meta = dict(conversation.metadata or {})
        merged_meta['labels_reconcile'] = {
            'at': now,
            'instance': instance.instance_name,
            'labels': labels,
        }
        conversation.metadata = merged_meta
        conversation.save(update_fields=update_fields)
        stats['updated'] += 1

    def _consume_response(response_payload: dict[str, Any]) -> int:
        count = 0
        for node in _iter_contact_like_nodes(response_payload):
            count += 1
            _upsert_from_node(node)
        return count

    for page in range(1, max(1, int(max_pages)) + 1):
        had_any = False
        try:
            contacts_resp = client.find_contacts(page=page, offset=page_size, where={})
            found = _consume_response(contacts_resp)
            had_any = had_any or (found > 0)
        except Exception as exc:
            stats['api_errors'] += 1
            logger.debug('findContacts falhou (page=%s): %s', page, exc)

        if not had_any:
            try:
                chats_resp = client.find_chats(page=page, offset=page_size, where={})
                found = _consume_response(chats_resp)
                had_any = had_any or (found > 0)
            except Exception as exc:
                stats['api_errors'] += 1
                logger.debug('findChats falhou (page=%s): %s', page, exc)

        stats['pages'] = page
        if not had_any:
            break

    if clear_missing and seen_jids:
        for conversation in WhatsAppConversation.objects.all().only('id', 'wa_id', 'wa_id_alt', 'etiquetas', 'metadata'):
            jid = normalize_wa_id(conversation.wa_id or conversation.wa_id_alt or '')
            if not jid or jid not in seen_jids:
                continue
            remote_labels = labels_by_jid.get(jid, [])
            if remote_labels:
                continue
            if not (conversation.etiquetas or []):
                continue
            if dry_run:
                stats['updated'] += 1
                stats['cleared_labels'] += 1
                continue
            merged_meta = dict(conversation.metadata or {})
            merged_meta['labels_reconcile'] = {
                'at': now,
                'instance': instance.instance_name,
                'labels': [],
                'cleared': True,
            }
            conversation.etiquetas = []
            conversation.metadata = merged_meta
            conversation.save(update_fields=['etiquetas', 'metadata', 'atualizado_em'])
            stats['updated'] += 1
            stats['cleared_labels'] += 1

    return stats


def _find_contact_snapshot_for_jids(
    *,
    instance: WhatsAppInstance | None,
    jid_candidates: list[str],
) -> dict[str, Any] | None:
    if not instance or not instance.pk:
        return None

    normalized_jids = []
    for raw in jid_candidates:
        jid = normalize_wa_id(str(raw or '').strip())
        if jid and jid not in normalized_jids:
            normalized_jids.append(jid)
    if not normalized_jids:
        return None

    numbers = []
    for jid in normalized_jids:
        if '@' in jid:
            digits = normalize_number(jid.split('@', 1)[0])
        else:
            digits = normalize_number(jid)
        if digits and digits not in numbers:
            numbers.append(digits)

    where_variants: list[dict[str, Any]] = []
    for jid in normalized_jids:
        where_variants.extend([
            {'remoteJid': jid},
            {'jid': jid},
            {'id': jid},
            {'wa_id': jid},
            {'waId': jid},
        ])
    for number in numbers:
        where_variants.extend([
            {'number': number},
            {'phone': number},
            {'phoneNumber': number},
        ])

    client = EvolutionAPIClient(instance=instance)

    def _match_node(node: dict[str, Any]) -> bool:
        node_jid = normalize_wa_id(_extract_contact_jid_from_node(node))
        if node_jid and node_jid in normalized_jids:
            return True
        node_digits = normalize_number((node_jid.split('@', 1)[0] if '@' in node_jid else node_jid) if node_jid else '')
        return bool(node_digits and node_digits in numbers)

    for where in where_variants:
        for fetch in (client.find_contacts, client.find_chats):
            try:
                response = fetch(where=where, page=1, offset=20)
            except Exception:
                continue
            for node in _iter_contact_like_nodes(response):
                if isinstance(node, dict) and _match_node(node):
                    return node
    return None


def reconcile_recent_outbound_statuses(*, minutes: int = 180, limit: int = 200, dry_run: bool = False) -> dict[str, int]:
    now = timezone.now()
    since = now - timedelta(minutes=max(1, int(minutes)))
    rows = (
        WhatsAppMessage.objects
        .select_related('conversa', 'conversa__instance')
        .filter(
            direcao=WhatsAppMessage.Direction.ENVIADA,
            criado_em__gte=since,
            external_id__isnull=False,
        )
        .exclude(external_id='')
        .filter(status__in=[WhatsAppMessage.Status.PENDENTE, WhatsAppMessage.Status.ENVIADA, WhatsAppMessage.Status.ENTREGUE])
        .order_by('-criado_em')[:max(1, int(limit))]
    )
    messages = list(rows)
    stats = {
        'checked': len(messages),
        'updated': 0,
        'failed_lookups': 0,
        'no_instance': 0,
        'no_match': 0,
    }
    if not messages:
        return stats

    grouped: dict[tuple[str, str], list[WhatsAppMessage]] = defaultdict(list)
    instance_cache: dict[str, WhatsAppInstance] = {}
    for msg in messages:
        conversa = msg.conversa
        instance = conversa.instance or get_active_instance()
        if not instance:
            stats['no_instance'] += 1
            continue
        remote_jid = normalize_wa_id(conversa.wa_id or conversa.wa_id_alt or '')
        if not remote_jid:
            stats['no_match'] += 1
            continue
        key = f'{instance.instance_name}::{remote_jid}'
        instance_cache[key] = instance
        grouped[(key, remote_jid)].append(msg)

    for (group_key, remote_jid), group_messages in grouped.items():
        instance = instance_cache.get(group_key)
        if not instance:
            stats['no_instance'] += len(group_messages)
            continue

        client = EvolutionAPIClient(instance=instance)
        remote_where = {'remoteJid': remote_jid}
        responses: list[dict[str, Any]] = []
        try:
            responses.append(client.find_status_message(where=remote_where, page=1, offset=120))
        except Exception:
            stats['failed_lookups'] += 1
        try:
            responses.append(client.find_messages(where=remote_where, page=1, offset=120))
        except Exception:
            stats['failed_lookups'] += 1

        status_by_id: dict[str, str] = {}
        for resp in responses:
            for node in _iter_dict_nodes(resp):
                candidate_status = map_delivery_status({'data': node})
                if not candidate_status:
                    continue
                for node_id in _extract_node_message_ids(node):
                    norm = normalize_message_id(node_id)
                    if not norm:
                        continue
                    existing = status_by_id.get(norm, '')
                    merged = merge_delivery_status(existing, candidate_status)
                    status_by_id[norm] = merged or candidate_status

        if not status_by_id:
            stats['no_match'] += len(group_messages)
            continue

        for msg in group_messages:
            current = str(msg.status or '').strip().lower()
            ext_norm = normalize_message_id(msg.external_id or '')
            if not ext_norm:
                stats['no_match'] += 1
                continue
            incoming = status_by_id.get(ext_norm, '')
            if not incoming:
                tail = ext_norm[-20:]
                for cand_norm, cand_status in status_by_id.items():
                    if not cand_norm or not cand_status:
                        continue
                    if cand_norm.endswith(tail) or ext_norm.endswith(cand_norm[-20:]):
                        incoming = merge_delivery_status(incoming, cand_status)
            if not incoming:
                stats['no_match'] += 1
                continue

            final_status = merge_delivery_status(current, incoming)
            if not final_status or final_status == current:
                continue

            if dry_run:
                stats['updated'] += 1
                continue

            merged_payload = dict(msg.payload or {})
            merged_payload['status_reconcile'] = {
                'at': now.isoformat(),
                'from': current,
                'to': final_status,
                'source': 'routine',
            }
            msg.status = final_status
            msg.payload = merged_payload
            msg.save(update_fields=['status', 'payload'])
            stats['updated'] += 1

    return stats


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
        data.get('keyId'),
        data.get('id'),
        data.get('messageId'),
        payload.get('keyId'),
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
        external_id_candidates.append(data.get('update', {}).get('keyId'))
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

    # Confirmacao de entrega/leitura so faz sentido para mensagens enviadas.
    if message.direcao != WhatsAppMessage.Direction.ENVIADA:
        return False

    final_status = merge_delivery_status(message.status, status)
    if final_status == (message.status or '') and isinstance(message.payload, dict) and message.payload.get('status_update'):
        return False

    merged_payload = dict(message.payload or {})
    merged_payload['status_update'] = payload
    message.status = final_status
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
        data.get('keyId'),
        data.get('id'),
        data.get('messageId'),
        payload.get('keyId'),
        payload.get('id'),
    ]
    if isinstance(data.get('update'), dict):
        update_key = data.get('update', {}).get('key', {})
        if isinstance(update_key, dict):
            external_id_candidates.append(update_key.get('id'))
        external_id_candidates.append(data.get('update', {}).get('keyId'))
    external_id_candidates = [str(v).strip() for v in external_id_candidates if v]

    message_obj = resolve_message_by_external_candidates(external_id_candidates) if external_id_candidates else None

    texto = parse_message_text(payload)
    texto = sanitize_text_content(texto)
    media_url, media_kind = parse_message_media(payload)
    raw_message = unwrap_message_content(data.get('message') if isinstance(data.get('message'), dict) else {})
    inferred_kind = infer_message_kind(raw_message, data, payload)
    self_jids = _extract_self_jids(payload, data, instance=message_obj.conversa.instance if message_obj and message_obj.conversa else None)
    from_me = resolve_from_me(payload, data, key_data, self_jids)
    expected_direction = WhatsAppMessage.Direction.ENVIADA if from_me else WhatsAppMessage.Direction.RECEBIDA

    if not message_obj:
        # Fallback para updates sem id/correlacao perfeita:
        # tenta anexar o update na ultima mensagem recebida "placeholder" da conversa.
        key_remote = data.get('key', {}) if isinstance(data.get('key'), dict) else {}
        remote_jid = str(
            key_remote.get('remoteJid')
            or key_remote.get('participant')
            or data.get('remoteJid')
            or data.get('from')
            or payload.get('remoteJid')
            or payload.get('from')
            or ''
        ).strip()
        remote_jid = normalize_wa_id(remote_jid) if remote_jid else ''
        conversation = None
        if remote_jid:
            conversation = (
                WhatsAppConversation.objects.filter(wa_id=remote_jid).first()
                or WhatsAppConversation.objects.filter(wa_id_alt=remote_jid).first()
            )
        if conversation:
            recent_cut = timezone.now() - timedelta(minutes=20)
            placeholders = [
                '',
                '[IMAGEM]',
                '[VIDEO]',
                '[AUDIO]',
                '[DOCUMENTO]',
                '[FIGURINHA]',
                '[Mensagem nao suportada]',
            ]
            message_obj = (
                conversation.mensagens.filter(
                    direcao=expected_direction,
                    criado_em__gte=recent_cut,
                    media_url='',
                    conteudo__in=placeholders,
                )
                .order_by('-criado_em')
                .first()
            )
        if not message_obj and conversation and from_me:
            candidate_kind = (media_kind or inferred_kind or '').strip().lower()
            fallback_text = texto
            if not fallback_text:
                fallback_text = {
                    'image': '[IMAGEM]',
                    'video': '[VIDEO]',
                    'audio': '[AUDIO]',
                    'document': '[DOCUMENTO]',
                    'sticker': '[FIGURINHA]',
                }.get(candidate_kind, '[Mensagem nao suportada]')
            ext_id = fit_external_id(external_id_candidates[0] if external_id_candidates else '')
            payload_snapshot = {'message_update': payload}
            status_value = merge_delivery_status(WhatsAppMessage.Status.ENVIADA, map_delivery_status(payload))
            if ext_id:
                message_obj, _ = WhatsAppMessage.objects.get_or_create(
                    external_id=ext_id,
                    defaults={
                        'conversa': conversation,
                        'direcao': expected_direction,
                        'conteudo': fallback_text,
                        'media_url': media_url or '',
                        'status': status_value,
                        'payload': payload_snapshot,
                    },
                )
            else:
                message_obj = WhatsAppMessage.objects.create(
                    conversa=conversation,
                    direcao=expected_direction,
                    conteudo=fallback_text,
                    media_url=media_url or '',
                    status=status_value,
                    payload=payload_snapshot,
                )
        if not message_obj:
            return False

    changed_fields: list[str] = []
    text_before = sanitize_text_content(message_obj.conteudo or '')

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
        # Prefere ids brutos do webhook (quando existir) para consultas na Evolution.
        # O external_id salvo no banco pode estar truncado para caber no campo.
        candidate_ids: list[str] = []
        for raw in external_id_candidates + [message_obj.external_id or '']:
            value = str(raw or '').strip()
            if value and value not in candidate_ids:
                candidate_ids.append(value)
        if not candidate_ids:
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

        from_me_hint = bool(
            (data.get('key', {}) if isinstance(data.get('key'), dict) else {}).get('fromMe')
            or message_obj.direcao == WhatsAppMessage.Direction.ENVIADA
        )
        raw_message_payload = data if isinstance(data, dict) else {}
        media_type_hint = (inferred_kind or media_kind or '').strip().lower()
        media_type_for_query = media_type_hint if media_type_hint in {'image', 'video', 'audio', 'document', 'sticker'} else ''
        raw_message_db_id = _find_nested_value(raw_message_payload, {'messageid'})
        message_db_id = int(raw_message_db_id) if str(raw_message_db_id).isdigit() else None

        client = EvolutionAPIClient(instance=instance)
        responses: list[dict[str, Any]] = []
        for external_id in candidate_ids[:6]:
            where_candidates = []
            where_candidates.append({'key': {'id': external_id}})
            where_candidates.append({'id': external_id})
            if remote_jid:
                where_candidates.append({'key': {'id': external_id, 'remoteJid': remote_jid, 'fromMe': from_me_hint}})
                where_candidates.append({'remoteJid': remote_jid, 'id': external_id})
            for where in where_candidates[:6]:
                try:
                    responses.append(client.find_messages(where=where, page=1, offset=20))
                except Exception as exc:
                    logger.debug('findMessages falhou para where=%s: %s', where, exc)
                try:
                    responses.append(client.find_status_message(where=where, page=1, offset=20))
                except Exception as exc:
                    logger.debug('findStatusMessage falhou para where=%s: %s', where, exc)

        normalized_candidates = [normalize_message_id(v) for v in candidate_ids if normalize_message_id(v)]
        for resp in responses:
            for node in _iter_dict_nodes(resp):
                candidate_id = ''
                if isinstance(node.get('key'), dict):
                    candidate_id = str(node.get('key', {}).get('id') or '')
                candidate_id = candidate_id or str(node.get('id') or node.get('messageId') or '')
                if candidate_id and normalized_candidates:
                    cand_norm = normalize_message_id(candidate_id)
                    matches = False
                    for ext_norm in normalized_candidates:
                        if cand_norm == ext_norm or cand_norm.endswith(ext_norm[-20:]) or ext_norm.endswith(cand_norm[-20:]):
                            matches = True
                            break
                    if not matches:
                        continue
                candidate_payload = {'data': node}
                found_url, found_kind = parse_message_media(candidate_payload)
                if found_url:
                    return found_url, (found_kind or inferred_kind or media_kind or '').lower()

        # Fallback final: solicita o base64 diretamente para Evolution usando o message id.
        # Isso cobre casos em que apenas file.enc/url temporaria e retornada nos webhooks/findMessages.
        key_hint = {
            'id': candidate_ids[0] if candidate_ids else '',
            'remoteJid': remote_jid,
            'fromMe': from_me_hint,
        }

        def _extract_base64_and_mime(root: Any) -> tuple[str, str]:
            if not isinstance(root, (dict, list)):
                return '', ''
            b64_keys = {'base64', 'mediabase64', 'filebase64', 'buffer', 'file', 'data'}
            mime_keys = {'mimetype', 'mediamimetype'}
            b64_val = _find_nested_value(root, b64_keys)
            mime_val = _find_nested_value(root, mime_keys)
            return str(b64_val or '').strip(), str(mime_val or '').strip().lower()

        def _extract_url_and_kind(root: Any) -> tuple[str, str]:
            if not isinstance(root, (dict, list)):
                return '', ''
            mime_hint = str(_find_nested_value(root, {'mimetype', 'mediamimetype'}) or '').strip().lower()
            kind_hint = ''
            if mime_hint.startswith('image/'):
                kind_hint = 'image'
            elif mime_hint.startswith('video/'):
                kind_hint = 'video'
            elif mime_hint.startswith('audio/'):
                kind_hint = 'audio'
            if isinstance(root, dict):
                direct_url = str(
                    root.get('url')
                    or root.get('mediaUrl')
                    or root.get('fileUrl')
                    or ''
                ).strip()
                if direct_url:
                    parsed_url, parsed_kind = parse_message_media({'data': {'url': direct_url, 'mimetype': mime_hint}})
                    if parsed_url:
                        return parsed_url, (parsed_kind or kind_hint or inferred_kind or media_kind or 'document').lower()
            for node in _iter_dict_nodes(root):
                parsed_url, parsed_kind = parse_message_media({'data': node})
                if parsed_url:
                    return parsed_url, (parsed_kind or kind_hint or inferred_kind or media_kind or 'document').lower()
            return '', ''

        for external_id in candidate_ids[:6]:
            # 1) Tenta S3 URL pronta da Evolution
            try:
                query_payload: dict[str, Any] = {}
                if message_db_id is not None:
                    query_payload['messageId'] = message_db_id
                if media_type_for_query:
                    query_payload['type'] = media_type_for_query
                s3_url_resp = client.get_s3_media_url(
                    external_id,
                    message_key={**key_hint, 'id': external_id},
                    message_payload=raw_message_payload,
                    query=query_payload,
                )
                found_url, found_kind = _extract_url_and_kind(s3_url_resp)
                if found_url:
                    _console_log(
                        f'Midia recuperada via s3/getMediaUrl: external_id={external_id} kind={found_kind or inferred_kind or media_kind}',
                        'INFO',
                    )
                    return found_url, (found_kind or inferred_kind or media_kind or 'document').lower()
            except Exception as exc:
                logger.debug('s3/getMediaUrl falhou para id=%s: %s', external_id, exc)

            # 2) Tenta S3 media (pode retornar URL ou base64 conforme config)
            try:
                query_payload = {}
                if message_db_id is not None:
                    query_payload['messageId'] = message_db_id
                if media_type_for_query:
                    query_payload['type'] = media_type_for_query
                s3_media_resp = client.get_s3_media(
                    external_id,
                    message_key={**key_hint, 'id': external_id},
                    message_payload=raw_message_payload,
                    query=query_payload,
                )
                found_url, found_kind = _extract_url_and_kind(s3_media_resp)
                if found_url:
                    _console_log(
                        f'Midia recuperada via s3/getMedia: external_id={external_id} kind={found_kind or inferred_kind or media_kind}',
                        'INFO',
                    )
                    return found_url, (found_kind or inferred_kind or media_kind or 'document').lower()
                s3_b64, s3_mime = _extract_base64_and_mime(s3_media_resp)
                if s3_b64:
                    inferred = (inferred_kind or media_kind or 'document').lower()
                    field_by_kind = {
                        'image': 'imageMessage',
                        'video': 'videoMessage',
                        'audio': 'audioMessage',
                        'document': 'documentMessage',
                        'sticker': 'stickerMessage',
                    }
                    target_field = field_by_kind.get(inferred, 'documentMessage')
                    candidate_payload = {
                        'data': {
                            'message': {
                                target_field: {
                                    'base64': s3_b64,
                                    'mimetype': s3_mime or 'application/octet-stream',
                                }
                            }
                        }
                    }
                    parsed_url, parsed_kind = parse_message_media(candidate_payload)
                    if parsed_url:
                        _console_log(
                            f'Midia recuperada via s3/getMedia(base64): external_id={external_id} kind={parsed_kind or inferred}',
                            'INFO',
                        )
                        return parsed_url, (parsed_kind or inferred).lower()

                # Quando getMedia retorna metadata (lista), busca URL assinada por ID da media.
                media_nodes = []
                if isinstance(s3_media_resp, list):
                    media_nodes = [item for item in s3_media_resp if isinstance(item, dict)]
                elif isinstance(s3_media_resp, dict):
                    if isinstance(s3_media_resp.get('data'), list):
                        media_nodes = [item for item in s3_media_resp.get('data') if isinstance(item, dict)]
                    elif isinstance(s3_media_resp.get('media'), list):
                        media_nodes = [item for item in s3_media_resp.get('media') if isinstance(item, dict)]

                for media_item in media_nodes[:6]:
                    media_id = str(media_item.get('id') or '').strip()
                    if not media_id:
                        continue
                    try:
                        s3_direct_url_resp = client.get_s3_media_url(
                            external_id,
                            message_key={**key_hint, 'id': external_id},
                            message_payload=raw_message_payload,
                            query={'id': media_id},
                        )
                    except Exception:
                        continue
                    found_direct_url, found_direct_kind = _extract_url_and_kind(s3_direct_url_resp)
                    if found_direct_url:
                        _console_log(
                            f'Midia recuperada via s3/getMedia + getMediaUrl(id): external_id={external_id} media_id={media_id}',
                            'INFO',
                        )
                        return found_direct_url, (found_direct_kind or inferred_kind or media_kind or 'document').lower()
            except Exception as exc:
                logger.debug('s3/getMedia falhou para id=%s: %s', external_id, exc)

            # 3) Fallback legado: getBase64FromMediaMessage
            try:
                convert_to_mp4 = (inferred_kind or media_kind or '').lower() == 'audio'
                _console_log(
                    f'Tentando fallback getBase64FromMediaMessage: external_id={external_id} convert_to_mp4={convert_to_mp4}',
                    'INFO',
                )
                base64_resp = client.get_base64_from_media_message(
                    external_id,
                    convert_to_mp4=convert_to_mp4,
                    message_key={**key_hint, 'id': external_id},
                    message_payload=raw_message_payload,
                )
            except Exception as exc:
                _console_log(f'getBase64FromMediaMessage falhou para id={external_id}: {exc}', 'WARN')
                continue

            if not isinstance(base64_resp, dict):
                continue

            b64_value, mime_hint = _extract_base64_and_mime(base64_resp)
            if not b64_value:
                _console_log(f'getBase64FromMediaMessage sem base64 para id={external_id}', 'WARN')
                continue

            inferred = (inferred_kind or media_kind or 'document').lower()
            field_by_kind = {
                'image': 'imageMessage',
                'video': 'videoMessage',
                'audio': 'audioMessage',
                'document': 'documentMessage',
                'sticker': 'stickerMessage',
            }
            target_field = field_by_kind.get(inferred, 'documentMessage')
            candidate_payload = {
                'data': {
                    'message': {
                        target_field: {
                            'base64': b64_value,
                            'mimetype': mime_hint or 'application/octet-stream',
                        }
                    }
                }
            }
            found_url, found_kind = parse_message_media(candidate_payload)
            if found_url:
                _console_log(
                    f'Midia recuperada via getBase64FromMediaMessage: external_id={external_id} kind={found_kind or inferred} url_ok=true',
                    'INFO',
                )
                return found_url, (found_kind or inferred).lower()
            _console_log(f'Fallback base64 nao gerou URL renderizavel para id={external_id}', 'WARN')
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
        _console_log(
            f'Atualizando media_url da mensagem: external_id={message_obj.external_id or (external_id_candidates[0] if external_id_candidates else "")} kind={media_kind or inferred_kind or ""}',
            'INFO',
        )
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

    merged_payload = dict(message_obj.payload or {})
    preview = extract_link_preview(payload, texto or text_before)
    preview_changed = False
    if preview:
        current_preview = merged_payload.get('link_preview')
        if not isinstance(current_preview, dict) or current_preview != preview:
            merged_payload['link_preview'] = preview
            preview_changed = True

    if not changed_fields and not preview_changed:
        return False

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
    profile_picture_url = str(
        data.get('profilePictureUrl')
        or data.get('profilePicUrl')
        or data.get('profilePicture')
        or ''
    ).strip()
    wuid = normalize_wa_id(str(data.get('wuid') or data.get('number') or '').strip())
    if profile_picture_url:
        merged['profile_picture_url'] = profile_picture_url
    if wuid:
        merged['wuid'] = wuid
    merged['connection_update'] = payload
    instance.ultima_resposta = merged
    instance.save(update_fields=['status_conexao', 'ultima_resposta', 'atualizado_em'])

    # Sincroniza avatar da conversa da propria instancia (auto-chat) quando houver.
    if profile_picture_url and wuid:
        conversation = (
            WhatsAppConversation.objects.filter(wa_id=wuid).first()
            or WhatsAppConversation.objects.filter(wa_id_alt=wuid).first()
        )
        if conversation and profile_picture_url != (conversation.avatar_url or ''):
            conversation.avatar_url = profile_picture_url
            conversation.save(update_fields=['avatar_url', 'atualizado_em'])
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

    wa_id, real_jid, lid_jid = _choose_conversation_jid(
        jid_candidates=jid_candidates,
        from_me=from_me,
        self_jids=self_jids,
    )
    labels = extract_labels(payload, data if isinstance(data, dict) else {})
    avatar_url = resolve_avatar_url(payload, data if isinstance(data, dict) else {})
    contact_name = fallback_contact_name_by_wa_id(
        resolve_contact_name(payload, data if isinstance(data, dict) else {}).strip(),
        wa_id,
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

    # Fallback: alguns contacts.update chegam sem avatar/labels completos.
    if not avatar_url or not labels:
        snapshot_instance = conversation.instance or get_active_instance()
        snapshot = _find_contact_snapshot_for_jids(
            instance=snapshot_instance,
            jid_candidates=[wa_id, real_jid, lid_jid, conversation.wa_id, conversation.wa_id_alt],
        )
        if isinstance(snapshot, dict):
            if not labels:
                labels = normalize_labels(
                    snapshot.get('labels')
                    or snapshot.get('tags')
                    or snapshot.get('tag')
                    or snapshot.get('label')
                )
            if not avatar_url:
                avatar_url = _extract_contact_avatar_from_node(snapshot)
            if not contact_name:
                contact_name = fallback_contact_name_by_wa_id(_extract_contact_name_from_node(snapshot), wa_id)

    update_fields = ['metadata', 'atualizado_em']
    if real_jid and conversation.wa_id != real_jid:
        collision = WhatsAppConversation.objects.filter(wa_id=real_jid).exclude(pk=conversation.pk).exists()
        if not collision:
            old_wa_id = conversation.wa_id
            conversation.wa_id = real_jid
            if is_lid_jid(old_wa_id) and not conversation.wa_id_alt:
                conversation.wa_id_alt = old_wa_id
            update_fields.append('wa_id')
    if lid_jid and lid_jid != conversation.wa_id and lid_jid != (conversation.wa_id_alt or ''):
        conversation.wa_id_alt = lid_jid
        update_fields.append('wa_id_alt')
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
    if state in {'online', 'available', 'active'}:
        return 'online'
    if state in {'composing', 'typing'}:
        return 'typing'
    if state in {'recording', 'recordingaudio', 'recording_audio'}:
        return 'recording'
    if state in {'paused', 'unavailable', 'idle', 'stop', 'offline'}:
        return ''
    return ''


def reconcile_presence_states(
    *,
    typing_seconds: int = 12,
    recording_seconds: int = 12,
    online_seconds: int = 45,
    limit: int = 1000,
    dry_run: bool = False,
) -> dict[str, int]:
    rows = (
        WhatsAppConversation.objects
        .exclude(metadata={})
        .order_by('-atualizado_em')[:max(1, int(limit))]
    )
    conversations = list(rows)
    now = timezone.now()
    stats = {
        'checked': len(conversations),
        'updated': 0,
        'typing_expired': 0,
        'recording_expired': 0,
        'online_expired': 0,
        'invalid_timestamp': 0,
        'without_presence': 0,
    }
    for convo in conversations:
        metadata = convo.metadata or {}
        if not isinstance(metadata, dict):
            stats['without_presence'] += 1
            continue
        presence = metadata.get('presence')
        if not isinstance(presence, dict):
            stats['without_presence'] += 1
            continue

        state = str(presence.get('state') or '').strip().lower()
        raw_updated_at = str(presence.get('updated_at') or '').strip()
        if not state or not raw_updated_at:
            stats['without_presence'] += 1
            continue

        updated_at = parse_datetime(raw_updated_at)
        if not updated_at:
            stats['invalid_timestamp'] += 1
            continue
        if timezone.is_naive(updated_at):
            updated_at = timezone.make_aware(updated_at)
        elapsed = (now - updated_at).total_seconds()

        should_clear = False
        if state == 'typing' and elapsed > max(1, int(typing_seconds)):
            should_clear = True
            stats['typing_expired'] += 1
        elif state == 'recording' and elapsed > max(1, int(recording_seconds)):
            should_clear = True
            stats['recording_expired'] += 1
        elif state == 'online' and elapsed > max(1, int(online_seconds)):
            should_clear = True
            stats['online_expired'] += 1

        if not should_clear:
            continue

        if dry_run:
            stats['updated'] += 1
            continue

        merged_meta = dict(metadata)
        merged_meta['presence'] = {
            'state': '',
            'updated_at': now.isoformat(),
            'expired_from': state,
        }
        convo.metadata = merged_meta
        convo.save(update_fields=['metadata', 'atualizado_em'])
        stats['updated'] += 1

    return stats


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

    def _extract_presence_jids(raw_node: Any) -> list[str]:
        found: list[str] = []

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    key_low = str(key or '').strip().lower()
                    if key_low in {'id', 'jid', 'remotejid', 'remotejidalt', 'participant', 'participantalt', 'from', 'sender'}:
                        if isinstance(value, str) and value.strip():
                            normalized = normalize_wa_id(value.strip())
                            if normalized and normalized not in found:
                                found.append(normalized)
                    if isinstance(value, (dict, list)):
                        _walk(value)
            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, (dict, list)):
                        _walk(item)

        _walk(raw_node)
        return found

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
            jid_candidates = []
            primary = normalize_wa_id(str(jid_key or ''))
            if primary:
                jid_candidates.append(primary)
            for extra_jid in _extract_presence_jids(presence_info):
                if extra_jid and extra_jid not in jid_candidates:
                    jid_candidates.append(extra_jid)
            fallback_id = normalize_wa_id(str(data.get('id') or payload.get('id') or ''))
            if fallback_id and fallback_id not in jid_candidates:
                jid_candidates.append(fallback_id)
            for jid in jid_candidates:
                updates.append((jid, state))
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
            jid_candidates = []
            if jid:
                jid_candidates.append(jid)
            for extra_jid in _extract_presence_jids(item):
                if extra_jid and extra_jid not in jid_candidates:
                    jid_candidates.append(extra_jid)
            for jid_item in jid_candidates:
                updates.append((jid_item, state))

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
    dedup_updates: list[tuple[str, str]] = []
    seen_update_keys = set()
    for jid_value, state_value in updates:
        key = (str(jid_value or ''), str(state_value or ''))
        if not key[0] or key in seen_update_keys:
            continue
        seen_update_keys.add(key)
        dedup_updates.append((key[0], key[1]))

    for jid, state in dedup_updates:
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
    def _is_temporary_media_url(url_value: str) -> bool:
        raw = str(url_value or '').strip().lower()
        if not raw:
            return False
        if any(token in raw for token in ['mmg.whatsapp.net', 'lookaside.fbsbx.com', 'cdn.whatsapp.net']):
            return True
        if any(token in raw for token in ['x-amz-signature=', 'x-amz-credential=', 'x-amz-algorithm=', 'x-amz-date=']):
            return True
        if '/o1/v/t24/' in raw or '/v/t24/' in raw or '/o1/v/t62/' in raw or '/v/t62/' in raw:
            return True
        if '.enc' in raw:
            return True
        return False

    event_name = str(payload.get('event') or '').upper()
    event_name_norm = re.sub(r'[^A-Z0-9]+', '_', event_name).strip('_')
    if event_name_norm in {'PRESENCE_UPDATE', 'PRESENCE_UPSERT', 'PRESENCE'}:
        if process_presence_update(payload, instance=instance):
            logger.info('Webhook de presenca processado.')
            return
    if event_name_norm in {
        'LABELS_ASSOCIATION',
        'LABELS_EDIT',
        'LABELS_UPDATE',
        'LABEL_UPDATE',
        'CONTACTS_UPDATE',
        'CONTACT_UPDATE',
    }:
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
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            nested_payload = dict(payload)
            nested_payload['data'] = item
            process_webhook_payload(nested_payload, instance=instance)
        return
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
    contato = fallback_contact_name_by_wa_id(contato, wa_id)
    avatar_url = resolve_avatar_url(payload, data)
    etiquetas = extract_labels(payload, data)
    is_facebook_ads, ads_metadata = detect_facebook_ads_origin(payload, data)
    if is_facebook_ads and 'facebook ads' not in {str(et).strip().lower() for et in etiquetas}:
        etiquetas.append('Facebook Ads')
    texto = parse_message_text(payload)
    media_url, media_kind = parse_message_media(payload)
    raw_message = unwrap_message_content(data.get('message') if isinstance(data.get('message'), dict) else {})
    inferred_kind = infer_message_kind(raw_message, data, payload) if isinstance(raw_message, dict) and raw_message else ''
    if not texto and not media_url:
        # Evita criar bolha vazia (apenas horario) quando webhook nao traz conteudo real.
        if isinstance(raw_message, dict) and raw_message:
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
    ext_id = fit_external_id(
        (
        key_data.get('id')
        or data.get('id')
        or payload.get('id')
        )
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

    payload_with_preview = payload
    if direction == WhatsAppMessage.Direction.RECEBIDA:
        preview = extract_link_preview(payload, texto)
        if preview:
            payload_with_preview = dict(payload or {})
            payload_with_preview['link_preview'] = preview

    existing_message = None
    if ext_id:
        existing_message = WhatsAppMessage.objects.filter(external_id=ext_id).first()

    defaults = {
        'conversa': conversation,
        'direcao': direction,
        'conteudo': texto,
        'media_url': media_url or '',
        'status': (
            merge_delivery_status(
                WhatsAppMessage.Status.ENVIADA,
                map_delivery_status(payload),
            ) if from_me else WhatsAppMessage.Status.LIDA
        ),
        'payload': payload_with_preview,
        'recebido_em': ts if direction == WhatsAppMessage.Direction.RECEBIDA else None,
    }

    if existing_message:
        # Quando webhook vier com URL .enc/temporaria, nao apagar a midia ja persistida.
        incoming_media_url = str(defaults.get('media_url') or '').strip()
        existing_media_url = str(existing_message.media_url or '').strip()
        if not incoming_media_url and existing_media_url:
            defaults['media_url'] = existing_message.media_url
        elif existing_media_url and incoming_media_url and _is_temporary_media_url(incoming_media_url):
            defaults['media_url'] = existing_message.media_url

        # Para mensagens enviadas, evita trocar conteudo valido por placeholder.
        placeholder_values = {
            '',
            '[IMAGEM]',
            '[VIDEO]',
            '[AUDIO]',
            '[DOCUMENTO]',
            '[FIGURINHA]',
            '[Mensagem nao suportada]',
        }
        incoming_content = str(defaults.get('conteudo') or '').strip()
        current_content = str(existing_message.conteudo or '').strip()
        if (
            direction == WhatsAppMessage.Direction.ENVIADA
            and current_content
            and incoming_content in placeholder_values
        ):
            defaults['conteudo'] = current_content

        # Mantem status mais avancado entre o atual e o recebido no webhook.
        defaults['status'] = merge_delivery_status(existing_message.status, defaults.get('status'))

        # Mescla payload para manter metadados de upload/reply ja gravados.
        merged_payload = dict(existing_message.payload or {})
        if isinstance(payload_with_preview, dict):
            merged_payload.update(payload_with_preview)
        defaults['payload'] = merged_payload

        if direction != WhatsAppMessage.Direction.RECEBIDA and existing_message.recebido_em:
            defaults['recebido_em'] = existing_message.recebido_em

    message_created = False
    if ext_id:
        _, message_created = WhatsAppMessage.objects.update_or_create(external_id=ext_id, defaults=defaults)
    else:
        WhatsAppMessage.objects.create(**defaults)
        message_created = True

    # Alguns provedores entregam a imagem em dois passos:
    # primeiro o upsert sem URL/base64 e depois a midia via lookup/update.
    # Faz um backfill imediato para reduzir bolhas quebradas.
    expected_media_kind = (media_kind or inferred_kind or '').lower()
    if not (media_url or '').strip() and expected_media_kind in {'image', 'video', 'audio', 'document', 'sticker'}:
        try:
            _console_log(
                f'Backfill imediato de midia iniciado: ext_id={ext_id or "(vazio)"} kind={expected_media_kind}',
                'INFO',
            )
            process_message_content_update(payload)
        except Exception as exc:
            logger.debug('Backfill imediato de midia falhou para ext_id=%s: %s', ext_id, exc)

    if direction == WhatsAppMessage.Direction.RECEBIDA and message_created:
        WhatsAppConversation.objects.filter(pk=conversation.pk).update(nao_lidas=F('nao_lidas') + 1)

    logger.info('Webhook WhatsApp processado: %s', conversation.wa_id)
