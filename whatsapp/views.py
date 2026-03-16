import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

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
        form = WhatsAppSendMessageForm(request.POST)
        conversa_id = request.POST.get('conversa_id')
        if not form.is_valid() or not conversa_id:
            messages.error(request, 'Mensagem invalida.')
            return redirect('whatsapp:inbox')

        conversa = get_object_or_404(WhatsAppConversation, pk=conversa_id)
        instance = conversa.instance or get_active_instance()
        if not instance:
            messages.error(request, 'Nenhuma instancia ativa configurada para envio via Evolution API.')
            return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")

        texto = form.cleaned_data['mensagem'].strip()
        nova_mensagem = WhatsAppMessage.objects.create(
            conversa=conversa,
            direcao=WhatsAppMessage.Direction.ENVIADA,
            conteudo=texto,
            status=WhatsAppMessage.Status.PENDENTE,
            enviado_por=request.user,
        )

        try:
            client = EvolutionAPIClient(instance=instance)
            response = client.send_text(number=conversa.wa_id.split('@')[0], text=texto)
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
            conversa.ultima_mensagem = texto[:500]
            conversa.ultima_mensagem_em = nova_mensagem.criado_em
            conversa.save()
            messages.success(request, 'Mensagem enviada com sucesso.')
        except Exception as exc:
            nova_mensagem.status = WhatsAppMessage.Status.FALHA
            nova_mensagem.payload = {'erro': str(exc)}
            nova_mensagem.save(update_fields=['status', 'payload'])
            messages.error(request, f'Falha ao enviar mensagem: {exc}')

        return redirect(f"{reverse('whatsapp:inbox')}?c={conversa.pk}")


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

        try:
            client = EvolutionAPIClient(instance)
            response = client.connection_state()
            state = (
                response.get('instance', {}).get('state')
                or response.get('state')
                or response.get('status')
                or 'desconhecido'
            )
            instance.status_conexao = str(state).lower()
            instance.ultima_resposta = response
            instance.save(update_fields=['status_conexao', 'ultima_resposta', 'atualizado_em'])
            messages.success(request, f'Status atualizado: {instance.status_conexao}.')
        except Exception as exc:
            messages.error(request, f'Erro ao consultar status: {exc}')

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
