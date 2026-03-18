import json
import mimetypes
import os
import re
import uuid
import base64
import binascii
from datetime import timedelta
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.utils.dateparse import parse_datetime

from crmspagi.storage_backends import PublicMediaStorage
from usuarios.permissions import has_module_access

from .forms import (
    WhatsAppConnectForm,
    WhatsAppInstanceForm,
    WhatsAppSendMessageForm,
    WhatsAppStartConversationForm,
)
from .models import WhatsAppConversation, WhatsAppInstance, WhatsAppMessage
from .services import (
    EvolutionAPIClient,
    extract_qr_base64,
    fit_external_id,
    get_active_instance,
    normalize_number,
    normalize_wa_id,
    process_webhook_payload,
)


def _is_ajax_request(request) -> bool:
    accept = (request.headers.get('Accept') or '').lower()
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.POST.get('ajax') == '1'
        or 'application/json' in accept
    )


def _visible_text(value: str) -> str:
    text = str(value or '')
    text = re.sub(r'[\u200b\u200c\u200d\ufeff\u200e\u200f]', '', text)
    return text.strip()


def _normalize_public_media_url(value: str) -> str:
    candidate = str(value or '').strip()
    if not candidate:
        return ''
    lowered = candidate.lower()
    if lowered.startswith('data:'):
        return candidate
    if candidate.startswith('//'):
        return f'https:{candidate}'
    if lowered.startswith('http://') or lowered.startswith('https://'):
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
    if len(data_bytes) > 12 and data_bytes[4:8] == b'ftyp':
        return 'video/mp4'
    if head.startswith(b'\x1aE\xdf\xa3'):
        return 'video/webm'
    if head[:3] == b'ID3' or (len(head) > 2 and (head[0] == 0xFF and (head[1] & 0xE0) == 0xE0)):
        return 'audio/mpeg'
    if head.startswith(b'PK\x03\x04'):
        return 'application/zip'
    return ''


def _is_noise_status_message(message: WhatsAppMessage) -> bool:
    content = _visible_text(message.conteudo or '')
    has_media = bool(_normalize_public_media_url(message.media_url or ''))
    if not content and not has_media and message.direcao != WhatsAppMessage.Direction.SISTEMA:
        return True
    if content or has_media:
        return False
    if message.direcao != WhatsAppMessage.Direction.ENVIADA:
        return False
    if message.status not in {
        WhatsAppMessage.Status.ENVIADA,
        WhatsAppMessage.Status.ENTREGUE,
        WhatsAppMessage.Status.LIDA,
    }:
        return False
    payload = message.payload or {}
    if isinstance(payload, dict):
        if payload.get('status_update'):
            return True
        event = str(payload.get('event') or '').upper()
        if event in {'SEND_MESSAGE', 'MESSAGE_STATUS', 'MESSAGES_UPDATE', 'MESSAGE_UPDATE'}:
            return True
    return True


def _presence_info(conversation: WhatsAppConversation) -> tuple[str, str]:
    metadata = conversation.metadata or {}
    if not isinstance(metadata, dict):
        return '', ''
    presence = metadata.get('presence')
    if not isinstance(presence, dict):
        return '', ''
    state = str(presence.get('state') or '').strip().lower()
    raw_updated_at = str(presence.get('updated_at') or '').strip()
    if not state or not raw_updated_at:
        return '', ''
    updated_at = parse_datetime(raw_updated_at)
    if not updated_at:
        return '', ''
    if timezone.is_naive(updated_at):
        updated_at = timezone.make_aware(updated_at)
    elapsed = timezone.now() - updated_at
    if state == 'online':
        if elapsed > timedelta(seconds=75):
            return '', ''
        return 'online', 'online'
    if elapsed > timedelta(seconds=15):
        return '', ''
    if state == 'typing':
        return 'typing', 'digitando...'
    if state == 'recording':
        return 'recording', 'gravando audio...'
    return '', ''


def _message_reaction_emoji(message: WhatsAppMessage) -> str:
    payload = message.payload or {}
    if not isinstance(payload, dict):
        return ''
    last_reaction = payload.get('last_reaction')
    if isinstance(last_reaction, dict):
        emoji = _visible_text(last_reaction.get('emoji') or '')
        if emoji:
            return emoji
    reaction_sent = payload.get('reaction_sent')
    if isinstance(reaction_sent, dict):
        emoji = _visible_text(reaction_sent.get('emoji') or '')
        if emoji:
            return emoji
    reactions = payload.get('reactions')
    if isinstance(reactions, list):
        for item in reversed(reactions):
            if isinstance(item, dict):
                emoji = _visible_text(item.get('emoji') or '')
                if emoji:
                    return emoji
    return ''


def _message_link_preview(message: WhatsAppMessage) -> dict:
    payload = message.payload or {}
    if not isinstance(payload, dict):
        return {}
    preview = payload.get('link_preview')
    if not isinstance(preview, dict):
        return {}
    url = _visible_text(preview.get('url') or '')
    if not url:
        return {}
    return {
        'url': url,
        'title': _visible_text(preview.get('title') or ''),
        'description': _visible_text(preview.get('description') or ''),
        'image': _visible_text(preview.get('image') or ''),
        'site_name': _visible_text(preview.get('site_name') or ''),
    }


def _message_is_edited(message: WhatsAppMessage) -> bool:
    def _has_edit_marker(node) -> bool:
        if isinstance(node, dict):
            for raw_key, value in node.items():
                key = re.sub(r'[^a-z0-9]+', '', str(raw_key or '').lower())
                if key in {'editedmessage', 'editedmessagev2', 'editedmessagev2extension'}:
                    return True
                if key == 'protocolmessage' and isinstance(value, dict):
                    raw_type = value.get('type')
                    as_text = str(raw_type or '').strip().lower()
                    if as_text in {'14', 'message_edit', 'editedmessage', 'edit'}:
                        return True
                    try:
                        if int(raw_type) == 14:
                            return True
                    except (TypeError, ValueError):
                        pass
                if _has_edit_marker(value):
                    return True
        elif isinstance(node, list):
            for item in node:
                if _has_edit_marker(item):
                    return True
        return False

    payload = message.payload or {}
    if not isinstance(payload, dict):
        return False
    if isinstance(payload.get('edited_local'), dict):
        return True
    message_update = payload.get('message_update')
    if isinstance(message_update, dict) and _has_edit_marker(message_update):
        return True
    return False


def _find_string_in_nested_payload(node, keys: set[str]) -> str:
    if isinstance(node, dict):
        for k, v in node.items():
            key = str(k or '').strip().lower()
            if key in keys and isinstance(v, (str, int, float)):
                value = str(v).strip()
                if value:
                    return value
            nested = _find_string_in_nested_payload(v, keys)
            if nested:
                return nested
    elif isinstance(node, list):
        for item in node:
            nested = _find_string_in_nested_payload(item, keys)
            if nested:
                return nested
    return ''


def _message_media_group_id(message: WhatsAppMessage) -> str:
    payload = message.payload or {}
    if not isinstance(payload, dict):
        return ''
    keys = {
        'mediagroupid',
        'media_group_id',
        'albumid',
        'album_id',
        'groupid',
        'group_id',
    }
    found = _find_string_in_nested_payload(payload, keys)
    return found[:120] if found else ''


def _extract_text_from_message_node(node) -> str:
    if not isinstance(node, dict):
        return ''
    if _visible_text(node.get('conversation') or ''):
        return _visible_text(node.get('conversation') or '')
    ext = node.get('extendedTextMessage')
    if isinstance(ext, dict) and _visible_text(ext.get('text') or ''):
        return _visible_text(ext.get('text') or '')
    image = node.get('imageMessage')
    if isinstance(image, dict) and _visible_text(image.get('caption') or ''):
        return _visible_text(image.get('caption') or '')
    video = node.get('videoMessage')
    if isinstance(video, dict) and _visible_text(video.get('caption') or ''):
        return _visible_text(video.get('caption') or '')
    return ''


def _message_reply_preview(message: WhatsAppMessage) -> dict:
    payload = message.payload or {}
    if not isinstance(payload, dict):
        return {}

    # Resposta local (mensagens enviadas a partir do CRM)
    local_reply = payload.get('reply_to')
    if isinstance(local_reply, dict):
        text_preview = _visible_text(local_reply.get('text_preview') or '')
        media_kind = _visible_text(local_reply.get('media_kind') or '')
        if not text_preview and media_kind:
            text_preview = f'[{media_kind.upper()}]'
        if text_preview:
            author = 'Voce'
            message_pk = str(local_reply.get('message_pk') or '')
            if message_pk.isdigit():
                quoted_msg = message.conversa.mensagens.filter(pk=int(message_pk)).first()
                if quoted_msg and quoted_msg.direcao == WhatsAppMessage.Direction.RECEBIDA:
                    author = message.conversa.nome_exibicao or 'Contato'
            return {
                'author': author,
                'text': text_preview[:220],
            }

    # Resposta recebida (contextInfo no payload do webhook)
    data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    message_node = data.get('message') if isinstance(data.get('message'), dict) else {}
    if not isinstance(message_node, dict):
        return {}

    candidates = []
    for key in (
        'extendedTextMessage',
        'imageMessage',
        'videoMessage',
        'documentMessage',
        'audioMessage',
        'stickerMessage',
    ):
        part = message_node.get(key)
        if isinstance(part, dict):
            candidates.append(part.get('contextInfo'))
            nested = part.get('messageContextInfo')
            if isinstance(nested, dict):
                candidates.append(nested)
    if isinstance(message_node.get('messageContextInfo'), dict):
        candidates.append(message_node.get('messageContextInfo'))

    context_info = next((c for c in candidates if isinstance(c, dict)), {})
    if not context_info:
        return {}

    stanza_id = _visible_text(context_info.get('stanzaId') or context_info.get('quotedStanzaID') or '')
    quoted_participant = normalize_wa_id(_visible_text(context_info.get('participant') or context_info.get('quotedParticipant') or ''))
    quoted_message = context_info.get('quotedMessage') if isinstance(context_info.get('quotedMessage'), dict) else {}

    preview_text = _extract_text_from_message_node(quoted_message)
    if not preview_text and isinstance(quoted_message, dict):
        if isinstance(quoted_message.get('imageMessage'), dict):
            preview_text = '[Foto]'
        elif isinstance(quoted_message.get('videoMessage'), dict):
            preview_text = '[Video]'
        elif isinstance(quoted_message.get('audioMessage'), dict):
            preview_text = '[Audio]'
        elif isinstance(quoted_message.get('stickerMessage'), dict):
            preview_text = '[Figurinha]'
        elif isinstance(quoted_message.get('documentMessage'), dict):
            preview_text = '[Documento]'

    if not preview_text and stanza_id:
        quoted_msg = (
            message.conversa.mensagens.filter(external_id=stanza_id).first()
            or message.conversa.mensagens.filter(external_id__iendswith=stanza_id).first()
        )
        if quoted_msg:
            preview_text = _visible_text(quoted_msg.conteudo or '')
            if not preview_text:
                mk = (quoted_msg.media_kind or '').strip().lower()
                if mk == 'image':
                    preview_text = '[Foto]'
                elif mk == 'video':
                    preview_text = '[Video]'
                elif mk == 'audio':
                    preview_text = '[Audio]'
                elif mk == 'sticker':
                    preview_text = '[Figurinha]'
                elif mk == 'document':
                    preview_text = '[Documento]'

    if not preview_text:
        return {}

    author = 'Contato'
    quoted_msg_by_id = None
    if stanza_id:
        quoted_msg_by_id = (
            message.conversa.mensagens.filter(external_id=stanza_id).first()
            or message.conversa.mensagens.filter(external_id__iendswith=stanza_id).first()
        )
    if quoted_msg_by_id:
        author = 'Voce' if quoted_msg_by_id.direcao == WhatsAppMessage.Direction.ENVIADA else (message.conversa.nome_exibicao or 'Contato')
    elif quoted_participant:
        conversation_jids = {normalize_wa_id(message.conversa.wa_id or ''), normalize_wa_id(message.conversa.wa_id_alt or '')}
        if quoted_participant not in conversation_jids:
            author = 'Voce'

    return {
        'author': author,
        'text': preview_text[:220],
    }


def _message_key_data(message: WhatsAppMessage) -> tuple[str, bool, str]:
    payload = message.payload or {}
    key_data = {}
    if isinstance(payload.get('data'), dict) and isinstance(payload.get('data', {}).get('key'), dict):
        key_data = payload.get('data', {}).get('key', {})
    elif isinstance(payload.get('key'), dict):
        key_data = payload.get('key', {})

    conversa = message.conversa
    remote_jid = (
        key_data.get('remoteJid')
        or key_data.get('participant')
        or conversa.wa_id
        or conversa.wa_id_alt
        or ''
    )
    if '@' not in remote_jid:
        remote_jid = normalize_wa_id(remote_jid)

    from_me = key_data.get('fromMe')
    if from_me is None:
        from_me = (message.direcao == WhatsAppMessage.Direction.ENVIADA)

    message_id = (
        message.external_id
        or key_data.get('id')
        or payload.get('id')
        or payload.get('messageId')
    )
    data_payload = payload.get('data', {}) if isinstance(payload.get('data'), dict) else {}
    message_id = (
        message_id
        or data_payload.get('id')
        or data_payload.get('messageId')
        or (data_payload.get('key', {}) or {}).get('id')
    )
    message_payload = data_payload.get('message', {}) if isinstance(data_payload.get('message'), dict) else {}
    if not message_id and isinstance(message_payload.get('key'), dict):
        message_id = message_payload.get('key', {}).get('id')

    return str(remote_jid or ''), bool(from_me), str(message_id or '')


def can_manage_whatsapp_instance(user) -> bool:
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return getattr(profile, 'nivel_acesso', '') == 'ADMIN'


def can_archive_whatsapp_conversation(user) -> bool:
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return getattr(profile, 'nivel_acesso', '') == 'GERENTE'


def ensure_br_country_code(number: str) -> str:
    digits = normalize_number(number or '')
    if not digits:
        return digits
    if digits.startswith('55'):
        return digits
    if len(digits) in {10, 11}:
        return f'55{digits}'
    return digits


def _resolve_sender_display_name(user) -> str:
    if not user:
        return ''
    full_name = ''
    if hasattr(user, 'get_full_name'):
        full_name = (user.get_full_name() or '').strip()
    if full_name:
        return full_name
    first_name = (getattr(user, 'first_name', '') or '').strip()
    last_name = (getattr(user, 'last_name', '') or '').strip()
    if first_name or last_name:
        return f'{first_name} {last_name}'.strip()
    profile = getattr(user, 'profile', None)
    for key in ('nome_completo', 'nome', 'full_name'):
        value = (getattr(profile, key, '') or '').strip() if profile else ''
        if value:
            return value
    return (getattr(user, 'username', '') or '').strip()


def _apply_seller_signature(user, text: str) -> str:
    body = _visible_text(text or '')
    if not body:
        return ''
    sender_name = _resolve_sender_display_name(user)
    if not sender_name:
        return body
    prefix = f'*{sender_name}:*'
    first_line = (body.splitlines()[0] if body else '').strip()
    if first_line.lower() == prefix.lower() or body.startswith(prefix):
        return body
    return f'{prefix}\n{body}'


def _refresh_conversation_preview(conversa: WhatsAppConversation) -> None:
    latest = conversa.mensagens.order_by('-criado_em').first()
    if latest:
        preview = _visible_text(latest.conteudo or '')
        if not preview and (latest.media_url or '').strip():
            kind = (latest.media_kind or '').strip().lower()
            preview = {
                'image': '[IMAGEM]',
                'video': '[VIDEO]',
                'audio': '[AUDIO]',
                'sticker': '[FIGURINHA]',
                'document': '[DOCUMENTO]',
            }.get(kind, '[ARQUIVO]')
        conversa.ultima_mensagem = (preview or '')[:500]
        conversa.ultima_mensagem_em = latest.criado_em or timezone.now()
    else:
        conversa.ultima_mensagem = ''
        conversa.ultima_mensagem_em = timezone.now()

    in_count = conversa.mensagens.filter(direcao=WhatsAppMessage.Direction.RECEBIDA).count()
    conversa.nao_lidas = min(int(conversa.nao_lidas or 0), int(in_count))
    conversa.save(update_fields=['ultima_mensagem', 'ultima_mensagem_em', 'nao_lidas', 'atualizado_em'])


class WhatsAppAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return has_module_access(self.request.user, 'whatsapp')


class WhatsAppInstanceAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_manage_whatsapp_instance(self.request.user)


class WhatsAppInboxView(WhatsAppAccessMixin, TemplateView):
    template_name = 'whatsapp/inbox.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip()

        conversas = WhatsAppConversation.objects.all()
        if query:
            conversas = conversas.filter(Q(nome_contato__icontains=query) | Q(wa_id__icontains=query))
        conversas = conversas.order_by('-ultima_mensagem_em')
        for convo in conversas:
            p_state, p_text = _presence_info(convo)
            setattr(convo, 'presence_state', p_state)
            setattr(convo, 'presence_text', p_text)
        conversas_ativas = [c for c in conversas if not c.arquivada]
        conversas_arquivadas = [c for c in conversas if c.arquivada]

        conversa_ativa = None
        mensagens = WhatsAppMessage.objects.none()
        active_presence_text = ''
        conversa_id = self.request.GET.get('c')
        if conversa_id and conversa_id.isdigit():
            conversa_ativa = get_object_or_404(WhatsAppConversation, pk=conversa_id)
            active_presence_text = _presence_info(conversa_ativa)[1]
            if conversa_ativa.nao_lidas:
                conversa_ativa.nao_lidas = 0
                conversa_ativa.save(update_fields=['nao_lidas'])
            raw_mensagens = list(conversa_ativa.mensagens.all().order_by('criado_em')[:500])
            filtered = []
            for m in raw_mensagens:
                if _is_noise_status_message(m):
                    continue
                m.conteudo = _visible_text(m.conteudo or '')
                m.media_url = _normalize_public_media_url(m.media_url or '')
                m.reaction_emoji = _message_reaction_emoji(m)
                m.link_preview = _message_link_preview(m)
                m.is_edited = _message_is_edited(m)
                m.media_group_id = _message_media_group_id(m)
                m.reply_preview = _message_reply_preview(m)
                filtered.append(m)
            mensagens = filtered[-300:]

        instance = get_active_instance()

        context.update(
            {
                'conversas': conversas[:200],
                'conversas_ativas': conversas_ativas[:200],
                'conversas_arquivadas': conversas_arquivadas[:200],
                'conversa_ativa': conversa_ativa,
                'mensagens': mensagens,
                'send_form': WhatsAppSendMessageForm(),
                'start_form': WhatsAppStartConversationForm(),
                'open_new_chat': False,
                'evolution_instance': instance,
                'active_presence_text': active_presence_text,
                'can_archive_conversation': can_archive_whatsapp_conversation(self.request.user),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        if action == 'start_conversation':
            return self._start_conversation(request)
        if action == 'send_message':
            return self._send_message(request)
        return redirect('whatsapp:inbox')

    def _start_conversation(self, request):
        is_ajax = _is_ajax_request(request)
        form = WhatsAppStartConversationForm(request.POST)
        if not form.is_valid():
            if is_ajax:
                errors = [str(e) for errs in form.errors.values() for e in errs]
                return JsonResponse({'ok': False, 'error': errors[0] if errors else 'Dados invalidos.'}, status=400)
            context = self.get_context_data()
            context['start_form'] = form
            context['open_new_chat'] = True
            return self.render_to_response(context)

        numero = ensure_br_country_code(form.cleaned_data['numero'])
        if not numero:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'Informe um numero valido no formato DDD + telefone.'}, status=400)
            form.add_error('numero', 'Informe um numero valido no formato DDD + telefone.')
            context = self.get_context_data()
            context['start_form'] = form
            context['open_new_chat'] = True
            return self.render_to_response(context)

        wa_id = normalize_wa_id(numero)
        fallback_nome = (form.cleaned_data.get('nome_contato') or '').strip() or numero
        conversa, _ = WhatsAppConversation.objects.get_or_create(
            wa_id=wa_id,
            defaults={
                'nome_contato': fallback_nome,
                'ultima_mensagem': 'Conversa iniciada no CRM.',
            },
        )
        if not conversa.nome_contato:
            conversa.nome_contato = fallback_nome
            conversa.save(update_fields=['nome_contato'])

        primeira_mensagem = _apply_seller_signature(
            request.user,
            (form.cleaned_data.get('primeira_mensagem') or '').strip(),
        )
        if primeira_mensagem:
            instance = conversa.instance or get_active_instance()
            if not instance:
                if is_ajax:
                    return JsonResponse({'ok': True, 'conversation_id': conversa.pk, 'warning': 'Conversa criada, mas sem instancia ativa para envio da primeira mensagem.'})
                messages.warning(request, 'Conversa criada, mas sem instancia ativa para envio da primeira mensagem.')
                return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")

            mensagem = WhatsAppMessage.objects.create(
                conversa=conversa,
                direcao=WhatsAppMessage.Direction.ENVIADA,
                conteudo=primeira_mensagem,
                status=WhatsAppMessage.Status.PENDENTE,
                enviado_por=request.user,
            )
            try:
                client = EvolutionAPIClient(instance=instance)
                response = client.send_text(number=numero, text=primeira_mensagem)
                external_id = fit_external_id(
                    (
                    response.get('key', {}).get('id')
                    or response.get('message', {}).get('key', {}).get('id')
                    or response.get('id')
                    )
                )
                if external_id:
                    mensagem.external_id = external_id
                mensagem.status = WhatsAppMessage.Status.ENVIADA
                mensagem.payload = response
                mensagem.save()

                if instance.pk:
                    conversa.instance = instance
                conversa.ultima_mensagem = primeira_mensagem[:500]
                conversa.ultima_mensagem_em = mensagem.criado_em
                conversa.save()
                messages.success(request, 'Conversa criada e primeira mensagem enviada.')
            except Exception as exc:
                mensagem.status = WhatsAppMessage.Status.FALHA
                mensagem.payload = {'erro': str(exc)}
                mensagem.save(update_fields=['status', 'payload'])
                if is_ajax:
                    return JsonResponse(
                        {
                            'ok': False,
                            'error': f'Conversa criada, mas falhou no envio da primeira mensagem: {exc}',
                            'conversation_id': conversa.pk,
                        },
                        status=400,
                    )
                form.add_error(None, f'Conversa criada, mas falhou no envio da primeira mensagem: {exc}')
                context = self.get_context_data()
                context['start_form'] = form
                context['open_new_chat'] = True
                context['conversa_ativa'] = conversa
                context['mensagens'] = conversa.mensagens.all().order_by('criado_em')[:300]
                context['conversas'] = WhatsAppConversation.objects.order_by('-ultima_mensagem_em')[:200]
                return self.render_to_response(context)

        if is_ajax:
            return JsonResponse({'ok': True, 'conversation_id': conversa.pk})
        return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")

    def _send_message(self, request):
        is_ajax = _is_ajax_request(request)
        form = WhatsAppSendMessageForm(request.POST, request.FILES)
        conversa_id = request.POST.get('conversa_id')
        if not conversa_id:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'Conversa invalida.'}, status=400)
            messages.error(request, 'Conversa invalida.')
            return redirect('whatsapp:inbox')

        if not form.is_valid():
            first_error = next(iter(form.errors.values()))[0] if form.errors else 'Mensagem invalida.'
            if is_ajax:
                return JsonResponse({'ok': False, 'error': str(first_error)}, status=400)
            messages.error(request, str(first_error))
            return redirect('whatsapp:inbox')

        conversa = get_object_or_404(WhatsAppConversation, pk=conversa_id)
        instance = conversa.instance or get_active_instance()
        if not instance:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'Nenhuma instancia ativa configurada para envio via Evolution API.'}, status=400)
            messages.error(request, 'Nenhuma instancia ativa configurada para envio via Evolution API.')
            return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")

        texto = _apply_seller_signature(
            request.user,
            (form.cleaned_data.get('mensagem') or '').strip(),
        )
        arquivo = form.cleaned_data.get('arquivo')
        reply_to_message_id_raw = (request.POST.get('reply_to_message_id') or '').strip()
        if not texto and not arquivo:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'Informe uma mensagem ou selecione um arquivo para enviar.'}, status=400)
            messages.error(request, 'Informe uma mensagem ou selecione um arquivo para enviar.')
            return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")

        media_url = ''
        media_storage_path = ''
        media_mimetype = ''
        media_name = ''
        media_kind = ''
        reply_to_message = None
        quoted_key_payload = None
        quoted_text_payload = ''
        if reply_to_message_id_raw.isdigit():
            reply_to_message = conversa.mensagens.filter(pk=int(reply_to_message_id_raw)).first()
            if reply_to_message:
                q_remote_jid, q_from_me, q_message_id = _message_key_data(reply_to_message)
                if q_message_id:
                    quoted_key_payload = {
                        'remoteJid': q_remote_jid or conversa.wa_id or '',
                        'fromMe': bool(q_from_me),
                        'id': q_message_id,
                    }
                    quoted_text_payload = _visible_text(reply_to_message.conteudo or '')
                    if not quoted_text_payload:
                        mk = (reply_to_message.media_kind or '').strip().lower()
                        quoted_text_payload = {
                            'image': '[Foto]',
                            'video': '[Video]',
                            'audio': '[Audio]',
                            'sticker': '[Figurinha]',
                            'document': '[Documento]',
                        }.get(mk, 'Mensagem')
        if arquivo:
            media_url, media_mimetype, media_name, media_storage_path = self._save_upload_and_get_url(arquivo)
            if media_url.startswith('//'):
                media_url = f'https:{media_url}'
            elif not media_url.lower().startswith(('http://', 'https://', 'data:')):
                normalized_local = media_url if media_url.startswith('/') else f'/{media_url.lstrip("/")}'
                media_url = request.build_absolute_uri(normalized_local)
            media_kind = self._resolve_media_kind(media_mimetype, media_name)

        nova_mensagem = WhatsAppMessage.objects.create(
            conversa=conversa,
            direcao=WhatsAppMessage.Direction.ENVIADA,
            conteudo=texto,
            media_url=media_url,
            status=WhatsAppMessage.Status.PENDENTE,
            enviado_por=request.user,
        )

        try:
            client = EvolutionAPIClient(instance=instance)
            number = ensure_br_country_code(conversa.wa_id.split('@')[0])
            if arquivo and media_kind == 'audio':
                response = client.send_whatsapp_audio(
                    number=number,
                    audio_url=media_url,
                    quoted_key=quoted_key_payload,
                    quoted_text=quoted_text_payload,
                )
            elif arquivo:
                response = client.send_media(
                    number=number,
                    media_url=media_url,
                    mediatype=media_kind,
                    mimetype=media_mimetype,
                    caption=texto,
                    file_name=media_name,
                    quoted_key=quoted_key_payload,
                    quoted_text=quoted_text_payload,
                )
            else:
                response = client.send_text(
                    number=number,
                    text=texto,
                    quoted_key=quoted_key_payload,
                    quoted_text=quoted_text_payload,
                )
            external_id = fit_external_id(
                (
                response.get('key', {}).get('id')
                or response.get('message', {}).get('key', {}).get('id')
                or response.get('id')
                )
            )
            if external_id:
                nova_mensagem.external_id = external_id
            nova_mensagem.status = WhatsAppMessage.Status.ENVIADA
            merged_payload = dict(response or {})
            if reply_to_message and quoted_key_payload:
                merged_payload['reply_to'] = {
                    'message_pk': reply_to_message.pk,
                    'external_id': reply_to_message.external_id or '',
                    'key': quoted_key_payload,
                    'text_preview': _visible_text(reply_to_message.conteudo or '')[:180],
                    'media_kind': (reply_to_message.media_kind or '').strip().lower(),
                }
            if arquivo:
                merged_payload['mimetype'] = media_mimetype
                merged_payload['mediaType'] = media_kind
                merged_payload['upload'] = {
                    'file_name': media_name,
                    'storage_path': media_storage_path,
                    'media_url': media_url,
                }
            nova_mensagem.payload = merged_payload
            nova_mensagem.save()

            if instance.pk:
                conversa.instance = instance
            if arquivo and texto:
                preview = f"[Arquivo] {media_name} - {texto}"
            elif arquivo:
                preview = f"[Arquivo] {media_name}"
            else:
                preview = texto
            conversa.ultima_mensagem = preview[:500]
            conversa.ultima_mensagem_em = nova_mensagem.criado_em
            conversa.save()
            if is_ajax:
                return JsonResponse({'ok': True, 'conversation_id': conversa.pk, 'message_id': nova_mensagem.pk})
            if arquivo:
                messages.success(request, 'Arquivo/midia enviado com sucesso.')
            else:
                messages.success(request, 'Mensagem enviada com sucesso.')
        except Exception as exc:
            nova_mensagem.status = WhatsAppMessage.Status.FALHA
            nova_mensagem.payload = {'erro': str(exc)}
            nova_mensagem.save(update_fields=['status', 'payload'])
            if media_storage_path:
                try:
                    default_storage.delete(media_storage_path)
                except Exception:
                    pass
            if is_ajax:
                return JsonResponse({'ok': False, 'error': f'Falha ao enviar mensagem: {exc}'}, status=400)
            messages.error(request, f'Falha ao enviar mensagem: {exc}')

        return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")

    @staticmethod
    def _resolve_media_kind(mimetype: str, file_name: str) -> str:
        mime = (mimetype or '').lower()
        name = (file_name or '').lower()
        ext = os.path.splitext(name)[1]
        audio_exts = {'.ogg', '.opus', '.webm', '.m4a', '.mp3', '.wav', '.aac'}
        if name.startswith('audio_') and ext in audio_exts:
            return 'audio'
        if mime.startswith('audio/'):
            return 'audio'
        if mime.startswith('image/'):
            return 'image'
        if mime.startswith('video/'):
            return 'video'
        if mime in {'application/octet-stream', 'binary/octet-stream'} and ext in audio_exts:
            return 'audio'
        guessed, _ = mimetypes.guess_type(file_name or '')
        guessed = (guessed or '').lower()
        if guessed.startswith('audio/'):
            return 'audio'
        if guessed.startswith('image/'):
            return 'image'
        if guessed.startswith('video/'):
            return 'video'
        return 'document'

    @staticmethod
    def _save_upload_and_get_url(uploaded_file):
        def _decode_data_url_payload(raw_data: bytes) -> tuple[bytes, str]:
            if not raw_data:
                return b'', ''
            try:
                text = raw_data.decode('utf-8', errors='ignore').strip()
            except Exception:
                return b'', ''
            if not text.lower().startswith('data:') or ';base64,' not in text.lower():
                return b'', ''
            try:
                header, encoded = text.split(',', 1)
            except ValueError:
                return b'', ''
            header_lower = header.lower()
            if not header_lower.startswith('data:') or ';base64' not in header_lower:
                return b'', ''
            mime = header[5:].split(';', 1)[0].strip().lower()
            if not mime.startswith(('image/', 'video/', 'audio/')):
                return b'', ''
            try:
                sanitized = re.sub(r'\s+', '', encoded or '')
                if len(sanitized) % 4:
                    sanitized += '=' * (4 - (len(sanitized) % 4))
                decoded = base64.b64decode(sanitized)
            except (binascii.Error, ValueError):
                return b'', ''
            return decoded, mime

        original_name = uploaded_file.name or ''
        ext = os.path.splitext(original_name)[1]
        try:
            raw_bytes = uploaded_file.read()
        except Exception:
            raw_bytes = b''

        decoded_bytes, decoded_mime = _decode_data_url_payload(raw_bytes)
        if decoded_bytes:
            raw_bytes = decoded_bytes

        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        detected_mime = _guess_mime_from_bytes(raw_bytes)
        mime_guess_by_name = mimetypes.guess_type(original_name or '')[0] or ''
        mime = decoded_mime or uploaded_file.content_type or mime_guess_by_name or detected_mime or 'application/octet-stream'
        if mime in {'application/octet-stream', 'binary/octet-stream'} and detected_mime:
            mime = detected_mime
        if not ext:
            ext = mimetypes.guess_extension(mime.split(';', 1)[0].strip().lower() or '') or ''
        unique_name = f"{uuid.uuid4().hex}{ext}"
        storage_path = f"whatsapp/uploads/{unique_name}"
        file_obj = ContentFile(raw_bytes, name=unique_name) if raw_bytes else uploaded_file
        try:
            storage = PublicMediaStorage()
            saved_path = storage.save(storage_path, file_obj)
            file_url = storage.url(saved_path)
        except Exception:
            fallback_obj = ContentFile(raw_bytes, name=unique_name) if raw_bytes else uploaded_file
            saved_path = default_storage.save(storage_path, fallback_obj)
            file_url = default_storage.url(saved_path)
        if mime in {'application/octet-stream', 'binary/octet-stream'}:
            lower_name = (original_name or '').lower()
            if lower_name.startswith('audio_') and ext.lower() in {'.ogg', '.opus', '.webm', '.m4a', '.mp3', '.wav', '.aac'}:
                mime = 'audio/ogg' if ext.lower() in {'.ogg', '.opus'} else 'audio/webm'
        return file_url, mime, original_name or unique_name, saved_path


@login_required
def mark_read(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden('Metodo nao permitido.')
    if not has_module_access(request.user, 'whatsapp'):
        return HttpResponseForbidden('Sem permissao.')

    conversa = get_object_or_404(WhatsAppConversation, pk=pk)
    conversa.nao_lidas = 0
    conversa.save(update_fields=['nao_lidas'])
    if _is_ajax_request(request):
        return JsonResponse({'ok': True, 'conversation_id': conversa.pk})
    return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")


@login_required
def delete_conversation(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden('Metodo nao permitido.')
    if not has_module_access(request.user, 'whatsapp'):
        return HttpResponseForbidden('Sem permissao.')

    conversa = get_object_or_404(WhatsAppConversation, pk=pk)
    conversa.delete()

    if _is_ajax_request(request):
        return JsonResponse({'ok': True})
    messages.success(request, 'Conversa deletada com sucesso.')
    return redirect('whatsapp:inbox')


@login_required
def archive_conversation(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden('Metodo nao permitido.')
    if not has_module_access(request.user, 'whatsapp'):
        return HttpResponseForbidden('Sem permissao.')
    if not can_archive_whatsapp_conversation(request.user):
        if _is_ajax_request(request):
            return JsonResponse({'ok': False, 'error': 'Somente gerente pode arquivar conversas.'}, status=403)
        return HttpResponseForbidden('Somente gerente pode arquivar conversas.')

    conversa = get_object_or_404(WhatsAppConversation, pk=pk)
    raw_action = (request.POST.get('archive_action') or request.POST.get('action') or '').strip().lower()
    if raw_action == 'unarchive':
        conversa.arquivada = False
    elif raw_action == 'archive':
        conversa.arquivada = True
    else:
        conversa.arquivada = not bool(conversa.arquivada)
    conversa.save(update_fields=['arquivada', 'atualizado_em'])

    if _is_ajax_request(request):
        return JsonResponse(
            {
                'ok': True,
                'conversation_id': conversa.pk,
                'arquivada': bool(conversa.arquivada),
            }
        )
    messages.success(request, 'Conversa arquivada com sucesso.' if conversa.arquivada else 'Conversa desarquivada com sucesso.')
    return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")


@login_required
def delete_message(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden('Metodo nao permitido.')
    if not has_module_access(request.user, 'whatsapp'):
        return HttpResponseForbidden('Sem permissao.')

    mensagem = get_object_or_404(WhatsAppMessage, pk=pk)
    conversa = mensagem.conversa
    deleted_id = mensagem.pk
    mensagem.delete()
    _refresh_conversation_preview(conversa)

    if _is_ajax_request(request):
        return JsonResponse({'ok': True, 'message_id': deleted_id, 'conversation_id': conversa.pk})
    messages.success(request, 'Mensagem deletada com sucesso.')
    return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")


@login_required
def edit_message(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden('Metodo nao permitido.')
    if not has_module_access(request.user, 'whatsapp'):
        return HttpResponseForbidden('Sem permissao.')

    mensagem = get_object_or_404(WhatsAppMessage, pk=pk)
    if mensagem.direcao != WhatsAppMessage.Direction.ENVIADA:
        return JsonResponse({'ok': False, 'error': 'Apenas mensagens enviadas podem ser editadas.'}, status=400)

    novo_texto = _visible_text(request.POST.get('mensagem') or request.POST.get('texto') or '')
    if not novo_texto:
        return JsonResponse({'ok': False, 'error': 'Informe o novo texto da mensagem.'}, status=400)

    texto_antigo = _visible_text(mensagem.conteudo or '')
    if novo_texto == texto_antigo:
        return JsonResponse({'ok': True, 'message_id': mensagem.pk, 'conteudo': mensagem.conteudo or '', 'is_edited': _message_is_edited(mensagem)})

    instance = mensagem.conversa.instance or get_active_instance()
    if not instance:
        return JsonResponse({'ok': False, 'error': 'Instancia ativa nao encontrada.'}, status=400)

    remote_jid, from_me, message_id = _message_key_data(mensagem)
    if not message_id:
        return JsonResponse({'ok': False, 'error': 'Nao foi possivel identificar o id da mensagem para editar.'}, status=400)

    try:
        client = EvolutionAPIClient(instance=instance)
        response = client.edit_message(
            remote_jid=remote_jid,
            from_me=from_me,
            message_id=message_id,
            text=novo_texto,
        )
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': f'Falha ao editar no WhatsApp: {exc}'}, status=400)

    merged_payload = dict(mensagem.payload or {})
    merged_payload['edited_local'] = {
        'old_text': texto_antigo,
        'new_text': novo_texto,
        'edited_at': timezone.now().isoformat(),
        'edited_by': getattr(request.user, 'username', ''),
        'remote': {
            'remote_jid': remote_jid,
            'from_me': from_me,
            'message_id': message_id,
            'response': response,
        },
    }
    mensagem.conteudo = novo_texto
    mensagem.payload = merged_payload
    mensagem.save(update_fields=['conteudo', 'payload'])

    _refresh_conversation_preview(mensagem.conversa)

    return JsonResponse({'ok': True, 'message_id': mensagem.pk, 'conteudo': mensagem.conteudo, 'is_edited': True})


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'payload invalido'}, status=400)

        event_name = (kwargs.get('event_name') or '').strip()
        if event_name and not payload.get('event'):
            payload['event'] = event_name.replace('-', '_').upper()

        instance_name = payload.get('instance') or request.headers.get('X-Evolution-Instance')
        if not instance_name and isinstance(payload.get('data'), dict):
            data = payload.get('data', {})
            raw_instance = data.get('instance')
            if isinstance(raw_instance, dict):
                instance_name = raw_instance.get('instanceName') or raw_instance.get('name')
            elif isinstance(raw_instance, str):
                instance_name = raw_instance

        instance = None
        if instance_name:
            instance = WhatsAppInstance.objects.filter(instance_name=instance_name).first()

        if instance and instance.webhook_secret:
            secret = request.headers.get('X-Webhook-Secret')
            if secret != instance.webhook_secret:
                return JsonResponse({'ok': False, 'error': 'assinatura invalida'}, status=403)

        process_webhook_payload(payload=payload, instance=instance)
        return JsonResponse({'ok': True})


class WhatsAppInstanceConfigView(WhatsAppInstanceAdminMixin, TemplateView):
    template_name = 'whatsapp/instance_config.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance_id = self.request.GET.get('instance')
        selected = None

        if instance_id and instance_id.isdigit():
            selected = WhatsAppInstance.objects.filter(pk=instance_id).first()
        if not selected:
            selected = WhatsAppInstance.objects.order_by('-atualizado_em').first()

        context['instances'] = WhatsAppInstance.objects.order_by('-atualizado_em')
        context['selected_instance'] = selected
        context['instance_form'] = WhatsAppInstanceForm(instance=selected)
        context['connect_form'] = WhatsAppConnectForm()
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        if action == 'save_instance':
            return self._save_instance(request)
        if action == 'create_remote':
            return self._create_remote(request)
        if action == 'connect_remote':
            return self._connect_remote(request)
        if action == 'refresh_status':
            return self._refresh_status(request)
        return redirect('whatsapp:instance_config')

    def _save_instance(self, request):
        instance_id = request.POST.get('instance_id')
        obj = WhatsAppInstance.objects.filter(pk=instance_id).first() if instance_id else None
        form = WhatsAppInstanceForm(request.POST, instance=obj)
        if form.is_valid():
            instance = form.save()
            messages.success(request, 'Instancia salva com sucesso.')
            return redirect(f"{reverse('whatsapp:instance_config')}?instance={instance.pk}")

        messages.error(request, 'Dados invalidos da instancia.')
        return self.render_to_response(
            {
                'instances': WhatsAppInstance.objects.order_by('-atualizado_em'),
                'selected_instance': obj,
                'instance_form': form,
                'connect_form': WhatsAppConnectForm(),
            }
        )

    def _create_remote(self, request):
        instance = self._load_instance_or_redirect(request)
        if not instance:
            return redirect('whatsapp:instance_config')

        try:
            client = EvolutionAPIClient(instance)
            response_create = client.create_instance(qrcode=True)
            qr = extract_qr_base64(response_create)
            if qr:
                instance.qr_code_base64 = qr

            webhook_url = request.build_absolute_uri(reverse('whatsapp:webhook_no_slash'))
            response_webhook = client.set_webhook(
                webhook_url=webhook_url,
                webhook_secret=instance.webhook_secret or '',
            )

            instance.ultima_resposta = {
                'create_instance': response_create,
                'set_webhook': response_webhook,
                'webhook_url': webhook_url,
            }
            instance.save(update_fields=['qr_code_base64', 'ultima_resposta', 'atualizado_em'])
            messages.success(request, 'Instancia criada e webhook configurado. Escaneie o QR Code.')
        except Exception as exc:
            messages.error(request, f'Erro ao criar instancia na Evolution API: {exc}')

        return redirect(f"{reverse('whatsapp:instance_config')}?instance={instance.pk}")

    def _connect_remote(self, request):
        instance = self._load_instance_or_redirect(request)
        if not instance:
            return redirect('whatsapp:instance_config')

        form = WhatsAppConnectForm(request.POST)
        numero = ''
        if form.is_valid():
            numero = form.cleaned_data.get('numero', '')

        try:
            client = EvolutionAPIClient(instance)
            response = client.connect_instance(number=numero)
            qr = extract_qr_base64(response)
            if qr:
                instance.qr_code_base64 = qr
            webhook_url = request.build_absolute_uri(reverse('whatsapp:webhook_no_slash'))
            response_webhook = client.set_webhook(
                webhook_url=webhook_url,
                webhook_secret=instance.webhook_secret or '',
            )
            instance.ultima_resposta = {
                'connect': response,
                'set_webhook': response_webhook,
                'webhook_url': webhook_url,
            }
            instance.save(update_fields=['qr_code_base64', 'ultima_resposta', 'atualizado_em'])
            messages.success(request, 'QR Code atualizado e webhook reaplicado. Escaneie com o WhatsApp.')
        except Exception as exc:
            messages.error(request, f'Erro ao conectar instancia: {exc}')

        return redirect(f"{reverse('whatsapp:instance_config')}?instance={instance.pk}")

    def _refresh_status(self, request):
        instance = self._load_instance_or_redirect(request)
        if not instance:
            return redirect('whatsapp:instance_config')

        result = _sync_instance_runtime(instance=instance, try_connect=False)
        if result.get('ok'):
            messages.success(request, f"Status atualizado: {result.get('status')}.")
        else:
            messages.error(request, f"Erro ao consultar status: {result.get('error')}")

        return redirect(f"{reverse('whatsapp:instance_config')}?instance={instance.pk}")

    @staticmethod
    def _load_instance_or_redirect(request):
        instance_id = request.POST.get('instance_id')
        if not instance_id or not instance_id.isdigit():
            messages.error(request, 'Selecione uma instancia.')
            return None
        instance = WhatsAppInstance.objects.filter(pk=instance_id).first()
        if not instance:
            messages.error(request, 'Instancia nao encontrada.')
            return None
        return instance


@login_required
def instance_runtime_status(request, pk):
    if not can_manage_whatsapp_instance(request.user):
        return JsonResponse({'ok': False, 'error': 'Sem permissao'}, status=403)

    instance = get_object_or_404(WhatsAppInstance, pk=pk)
    try_connect = request.GET.get('try_connect', '1') == '1'
    number = request.GET.get('number', '')
    result = _sync_instance_runtime(instance=instance, try_connect=try_connect, number=number)
    return JsonResponse(result)


def _sync_instance_runtime(instance: WhatsAppInstance, try_connect: bool, number: str = '') -> dict:
    try:
        client = EvolutionAPIClient(instance)
        response_state = client.connection_state()
        state = (
            response_state.get('instance', {}).get('state')
            or response_state.get('state')
            or response_state.get('status')
            or 'desconhecido'
        )
        state = str(state).lower()

        qr = instance.qr_code_base64 or ''
        response_connect = {}

        if try_connect and state not in {'open', 'connected'}:
            response_connect = client.connect_instance(number=number)
            new_qr = extract_qr_base64(response_connect)
            if new_qr:
                qr = new_qr
                instance.qr_code_base64 = new_qr

        instance.status_conexao = state
        instance.ultima_resposta = {
            'connectionState': response_state,
            'connect': response_connect,
        }
        instance.save(update_fields=['status_conexao', 'ultima_resposta', 'qr_code_base64', 'atualizado_em'])

        return {
            'ok': True,
            'status': state,
            'connected': state in {'open', 'connected'},
            'has_qr': bool(qr),
            'qr': qr,
        }
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


@login_required
def conversations_feed(request):
    if not has_module_access(request.user, 'whatsapp'):
        return JsonResponse({'ok': False, 'error': 'Sem permissao'}, status=403)

    query = (request.GET.get('q') or '').strip()
    conversas = WhatsAppConversation.objects.all()
    if query:
        conversas = conversas.filter(Q(nome_contato__icontains=query) | Q(wa_id__icontains=query))
    conversas = conversas.order_by('-ultima_mensagem_em')[:200]

    data = []
    for c in conversas:
        presence_state, presence_text = _presence_info(c)
        data.append(
            {
                'id': c.pk,
                'nome': c.nome_exibicao,
                'wa_id': c.wa_id,
                'wa_id_display': c.wa_id_display,
                'wa_id_alt': c.wa_id_alt or '',
                'avatar_url': c.avatar_url or '',
                'etiquetas': c.etiquetas or [],
                'ultima_mensagem': c.ultima_mensagem or '',
                'ultima_mensagem_em': c.ultima_mensagem_em.strftime('%d/%m %H:%M') if c.ultima_mensagem_em else '',
                'nao_lidas': c.nao_lidas or 0,
                'arquivada': bool(c.arquivada),
                'presence_state': presence_state,
                'presence_text': presence_text,
            }
        )
    return JsonResponse({'ok': True, 'conversas': data})


@login_required
def conversation_messages_feed(request, pk):
    if not has_module_access(request.user, 'whatsapp'):
        return JsonResponse({'ok': False, 'error': 'Sem permissao'}, status=403)

    conversa = get_object_or_404(WhatsAppConversation, pk=pk)
    mensagens = conversa.mensagens.all().order_by('criado_em')[:300]

    data = [
        {
            'id': m.pk,
            'direcao': m.direcao,
            'conteudo': _visible_text(m.conteudo or ''),
            'media_url': _normalize_public_media_url(m.media_url or ''),
            'media_kind': m.media_kind or '',
            'reaction_emoji': _message_reaction_emoji(m),
            'link_preview': _message_link_preview(m),
            'media_group_id': _message_media_group_id(m),
            'is_edited': _message_is_edited(m),
            'reply_preview': _message_reply_preview(m),
            'status_code': m.status,
            'status': m.get_status_display(),
            'criado_em': m.criado_em.strftime('%d/%m/%Y %H:%M') if m.criado_em else '',
            'can_react': True,
        }
        for m in mensagens
        if not _is_noise_status_message(m)
    ]
    return JsonResponse({'ok': True, 'mensagens': data})


@login_required
def react_message(request, pk):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo nao permitido'}, status=405)
    if not has_module_access(request.user, 'whatsapp'):
        return JsonResponse({'ok': False, 'error': 'Sem permissao'}, status=403)

    mensagem = get_object_or_404(WhatsAppMessage, pk=pk)
    emoji = (request.POST.get('emoji') or '').strip()
    if not emoji:
        return JsonResponse({'ok': False, 'error': 'Emoji obrigatorio'}, status=400)

    conversa = mensagem.conversa
    instance = conversa.instance or get_active_instance()
    if not instance:
        return JsonResponse({'ok': False, 'error': 'Instancia ativa nao encontrada'}, status=400)

    payload = mensagem.payload or {}
    remote_jid, from_me, message_id = _message_key_data(mensagem)
    if not message_id:
        return JsonResponse({'ok': False, 'error': 'Nao foi possivel identificar o id da mensagem para reagir'}, status=400)

    try:
        client = EvolutionAPIClient(instance=instance)
        response = client.send_reaction(
            remote_jid=remote_jid,
            from_me=bool(from_me),
            message_id=message_id,
            reaction=emoji,
        )
        merged_payload = dict(mensagem.payload or {})
        merged_payload['reaction_sent'] = {
            'emoji': emoji,
            'response': response,
        }
        mensagem.payload = merged_payload
        mensagem.save(update_fields=['payload'])
        return JsonResponse({'ok': True})
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)


def _forward_single_message(mensagem: WhatsAppMessage, numero: str, user):
    instance = mensagem.conversa.instance or get_active_instance()
    if not instance:
        raise ValueError('Instancia ativa nao encontrada')

    conteudo = _visible_text(mensagem.conteudo or '')
    if not conteudo:
        payload = mensagem.payload or {}
        if isinstance(payload, dict):
            data_payload = payload.get('data', {}) if isinstance(payload.get('data'), dict) else {}
            message_payload = data_payload.get('message', {}) if isinstance(data_payload.get('message'), dict) else {}
            fallback_text = (
                data_payload.get('text')
                or data_payload.get('body')
                or payload.get('text')
                or payload.get('body')
                or message_payload.get('conversation')
            )
            if isinstance(fallback_text, str):
                conteudo = _visible_text(fallback_text)
    media_url = _normalize_public_media_url(mensagem.media_url or '')
    media_kind = (mensagem.media_kind or '').strip().lower()

    placeholders = {'[imagem]', '[video]', '[audio]', '[documento]', '[document]', '[arquivo]', '[mensagem nao suportada]'}
    caption = ''
    if conteudo and conteudo.lower() not in placeholders:
        caption = conteudo

    client = EvolutionAPIClient(instance=instance)
    if media_url:
        if media_kind == 'audio':
            response = client.send_whatsapp_audio(number=numero, audio_url=media_url)
        else:
            parsed_path = urlparse(media_url).path or ''
            file_name = os.path.basename(parsed_path) or f'arquivo_{uuid.uuid4().hex}'
            guessed_mime = mimetypes.guess_type(parsed_path)[0] or ''
            if not guessed_mime:
                guessed_mime = 'image/webp' if media_kind == 'sticker' else (
                    'image/jpeg' if media_kind == 'image' else (
                    'video/mp4' if media_kind == 'video' else 'application/octet-stream'
                    )
                )
            response = client.send_media(
                number=numero,
                media_url=media_url,
                mediatype=('image' if media_kind == 'sticker' else media_kind) if media_kind in {'image', 'video', 'document', 'sticker'} else 'document',
                mimetype=guessed_mime,
                caption=caption,
                file_name=file_name,
            )
    else:
        if not conteudo:
            raise ValueError('Mensagem sem conteudo para encaminhar.')
        response = client.send_text(number=numero, text=conteudo)

    external_id = fit_external_id(
        (
        response.get('key', {}).get('id')
        or response.get('message', {}).get('key', {}).get('id')
        or response.get('id')
        )
    )

    wa_id = normalize_wa_id(numero)
    conversa_destino, _ = WhatsAppConversation.objects.get_or_create(
        wa_id=wa_id,
        defaults={'nome_contato': numero, 'ultima_mensagem': ''},
    )
    if instance.pk and not conversa_destino.instance:
        conversa_destino.instance = instance
    if not (conversa_destino.nome_contato or '').strip():
        conversa_destino.nome_contato = numero

    forward_preview = caption or conteudo
    if media_url and not forward_preview:
        forward_preview = {'image': '[IMAGEM]', 'video': '[VIDEO]', 'audio': '[AUDIO]', 'sticker': '[FIGURINHA]'}.get(media_kind, '[DOCUMENTO]')

    forwarded = WhatsAppMessage.objects.create(
        conversa=conversa_destino,
        external_id=external_id or None,
        direcao=WhatsAppMessage.Direction.ENVIADA,
        conteudo=forward_preview,
        media_url=media_url,
        status=WhatsAppMessage.Status.ENVIADA,
        enviado_por=user,
        payload={'forwarded_from_message_id': mensagem.pk, 'response': response},
    )
    conversa_destino.ultima_mensagem = (forward_preview or '')[:500]
    conversa_destino.ultima_mensagem_em = forwarded.criado_em
    conversa_destino.save()

    return conversa_destino, forwarded


@login_required
def forward_message(request, pk):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo nao permitido'}, status=405)
    if not has_module_access(request.user, 'whatsapp'):
        return JsonResponse({'ok': False, 'error': 'Sem permissao'}, status=403)

    mensagem = get_object_or_404(WhatsAppMessage, pk=pk)
    raw_number = (request.POST.get('numero') or request.POST.get('number') or '').strip()
    numero = ensure_br_country_code(raw_number)
    if not numero:
        return JsonResponse({'ok': False, 'error': 'Informe um numero valido para encaminhar.'}, status=400)

    try:
        conversa_destino, forwarded = _forward_single_message(mensagem, numero, request.user)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    return JsonResponse({'ok': True, 'conversation_id': conversa_destino.pk, 'message_id': forwarded.pk})


@login_required
def forward_messages_bulk(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo nao permitido'}, status=405)
    if not has_module_access(request.user, 'whatsapp'):
        return JsonResponse({'ok': False, 'error': 'Sem permissao'}, status=403)

    raw_number = (request.POST.get('numero') or request.POST.get('number') or '').strip()
    numero = ensure_br_country_code(raw_number)
    if not numero:
        return JsonResponse({'ok': False, 'error': 'Informe um numero valido para encaminhar.'}, status=400)

    raw_ids = (request.POST.get('ids') or '').strip()
    ids: list[int] = []
    for part in raw_ids.split(','):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    ids = list(dict.fromkeys(ids))[:30]
    if not ids:
        return JsonResponse({'ok': False, 'error': 'Selecione ao menos uma mensagem para encaminhar.'}, status=400)

    mensagens = list(WhatsAppMessage.objects.filter(pk__in=ids).order_by('criado_em'))
    if not mensagens:
        return JsonResponse({'ok': False, 'error': 'Mensagens selecionadas nao encontradas.'}, status=404)

    forwarded_count = 0
    last_conversation_id = None
    last_message_id = None
    errors: list[str] = []
    for msg in mensagens:
        try:
            conversa_destino, forwarded = _forward_single_message(msg, numero, request.user)
            forwarded_count += 1
            last_conversation_id = conversa_destino.pk
            last_message_id = forwarded.pk
        except Exception as exc:
            errors.append(str(exc))
            continue

    if forwarded_count == 0:
        error_detail = ''
        if errors:
            error_detail = errors[0]
        return JsonResponse(
            {
                'ok': False,
                'error': f'Nao foi possivel encaminhar as mensagens selecionadas.{(" Motivo: " + error_detail) if error_detail else ""}',
                'errors': errors[:5],
            },
            status=400,
        )

    return JsonResponse(
        {
            'ok': True,
            'forwarded_count': forwarded_count,
            'conversation_id': last_conversation_id,
            'message_id': last_message_id,
            'errors': errors[:5],
        }
    )
