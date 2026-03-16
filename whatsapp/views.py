import json
import mimetypes
import os
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.core.files.storage import default_storage
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

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
    get_active_instance,
    normalize_number,
    normalize_wa_id,
    process_webhook_payload,
)


class WhatsAppAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return has_module_access(self.request.user, 'whatsapp')


class WhatsAppInstanceAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or has_module_access(self.request.user, 'usuarios_admin')


class WhatsAppInboxView(WhatsAppAccessMixin, TemplateView):
    template_name = 'whatsapp/inbox.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip()

        conversas = WhatsAppConversation.objects.all()
        if query:
            conversas = conversas.filter(Q(nome_contato__icontains=query) | Q(wa_id__icontains=query))
        conversas = conversas.order_by('-ultima_mensagem_em')

        conversa_ativa = None
        mensagens = WhatsAppMessage.objects.none()
        conversa_id = self.request.GET.get('c')
        if conversa_id and conversa_id.isdigit():
            conversa_ativa = get_object_or_404(WhatsAppConversation, pk=conversa_id)
            mensagens = conversa_ativa.mensagens.all().order_by('criado_em')[:300]

        instance = get_active_instance()

        context.update(
            {
                'conversas': conversas[:200],
                'conversa_ativa': conversa_ativa,
                'mensagens': mensagens,
                'send_form': WhatsAppSendMessageForm(),
                'start_form': WhatsAppStartConversationForm(),
                'evolution_instance': instance,
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
        form = WhatsAppStartConversationForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Numero invalido para iniciar conversa.')
            return redirect('whatsapp:inbox')

        numero = normalize_number(form.cleaned_data['numero'])
        if not numero:
            messages.error(request, 'Informe um numero valido no formato DDI + DDD + telefone.')
            return redirect('whatsapp:inbox')

        wa_id = normalize_wa_id(numero)
        conversa, _ = WhatsAppConversation.objects.get_or_create(
            wa_id=wa_id,
            defaults={
                'nome_contato': form.cleaned_data.get('nome_contato', ''),
                'ultima_mensagem': 'Conversa iniciada no CRM.',
            },
        )
        if form.cleaned_data.get('nome_contato') and not conversa.nome_contato:
            conversa.nome_contato = form.cleaned_data['nome_contato']
            conversa.save(update_fields=['nome_contato'])

        return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")

    def _send_message(self, request):
        form = WhatsAppSendMessageForm(request.POST, request.FILES)
        conversa_id = request.POST.get('conversa_id')
        if not conversa_id:
            messages.error(request, 'Conversa invalida.')
            return redirect('whatsapp:inbox')

        if not form.is_valid():
            first_error = next(iter(form.errors.values()))[0] if form.errors else 'Mensagem invalida.'
            messages.error(request, str(first_error))
            return redirect('whatsapp:inbox')

        conversa = get_object_or_404(WhatsAppConversation, pk=conversa_id)
        instance = conversa.instance or get_active_instance()
        if not instance:
            messages.error(request, 'Nenhuma instancia ativa configurada para envio via Evolution API.')
            return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")

        texto = (form.cleaned_data.get('mensagem') or '').strip()
        arquivo = form.cleaned_data.get('arquivo')
        if not texto and not arquivo:
            messages.error(request, 'Informe uma mensagem ou selecione um arquivo para enviar.')
            return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")

        media_url = ''
        media_storage_path = ''
        media_mimetype = ''
        media_name = ''
        media_kind = ''
        if arquivo:
            media_url, media_mimetype, media_name, media_storage_path = self._save_upload_and_get_url(arquivo)
            if media_url.startswith('/'):
                media_url = request.build_absolute_uri(media_url)
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
            number = conversa.wa_id.split('@')[0]
            if arquivo and media_kind == 'audio':
                response = client.send_whatsapp_audio(number=number, audio_url=media_url)
            elif arquivo:
                response = client.send_media(
                    number=number,
                    media_url=media_url,
                    mediatype=media_kind,
                    mimetype=media_mimetype,
                    caption=texto,
                    file_name=media_name,
                )
            else:
                response = client.send_text(number=number, text=texto)
            external_id = (
                response.get('key', {}).get('id')
                or response.get('message', {}).get('key', {}).get('id')
                or response.get('id')
            )
            if external_id:
                nova_mensagem.external_id = external_id
            nova_mensagem.status = WhatsAppMessage.Status.ENVIADA
            nova_mensagem.payload = response
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
            messages.error(request, f'Falha ao enviar mensagem: {exc}')

        return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")

    @staticmethod
    def _resolve_media_kind(mimetype: str, file_name: str) -> str:
        mime = (mimetype or '').lower()
        if mime.startswith('audio/'):
            return 'audio'
        if mime.startswith('image/'):
            return 'image'
        if mime.startswith('video/'):
            return 'video'
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
        ext = os.path.splitext(uploaded_file.name or '')[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        storage_path = f"whatsapp/uploads/{unique_name}"
        try:
            storage = PublicMediaStorage()
            saved_path = storage.save(storage_path, uploaded_file)
            file_url = storage.url(saved_path)
        except Exception:
            saved_path = default_storage.save(storage_path, uploaded_file)
            file_url = default_storage.url(saved_path)
        mime = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name or '')[0] or 'application/octet-stream'
        return file_url, mime, uploaded_file.name or unique_name, saved_path


@login_required
def mark_read(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden('Metodo nao permitido.')
    if not has_module_access(request.user, 'whatsapp'):
        return HttpResponseForbidden('Sem permissao.')

    conversa = get_object_or_404(WhatsAppConversation, pk=pk)
    conversa.nao_lidas = 0
    conversa.save(update_fields=['nao_lidas'])
    return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'payload invalido'}, status=400)

        instance_name = payload.get('instance') or request.headers.get('X-Evolution-Instance')
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
            response = client.create_instance(qrcode=True)
            qr = extract_qr_base64(response)
            if qr:
                instance.qr_code_base64 = qr
            instance.ultima_resposta = response
            instance.save(update_fields=['qr_code_base64', 'ultima_resposta', 'atualizado_em'])
            messages.success(request, 'Instancia criada na Evolution API. Escaneie o QR Code.')
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
            instance.ultima_resposta = response
            instance.save(update_fields=['qr_code_base64', 'ultima_resposta', 'atualizado_em'])
            messages.success(request, 'QR Code atualizado. Escaneie com o WhatsApp.')
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
    if not (request.user.is_superuser or has_module_access(request.user, 'usuarios_admin')):
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

    data = [
        {
            'id': c.pk,
            'nome': c.nome_exibicao,
            'wa_id': c.wa_id,
            'ultima_mensagem': c.ultima_mensagem or '',
            'ultima_mensagem_em': c.ultima_mensagem_em.strftime('%d/%m %H:%M') if c.ultima_mensagem_em else '',
            'nao_lidas': c.nao_lidas or 0,
        }
        for c in conversas
    ]
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
            'conteudo': m.conteudo or '',
            'media_url': m.media_url or '',
            'status': m.get_status_display(),
            'criado_em': m.criado_em.strftime('%d/%m/%Y %H:%M') if m.criado_em else '',
        }
        for m in mensagens
    ]
    return JsonResponse({'ok': True, 'mensagens': data})
