from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Notificacao
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from webpush.models import WebPushDevice
from django.conf import settings

@login_required
def lista_notificacoes(request):
    # Marca todas as notificações como lidas ao acessar a página
    Notificacao.objects.filter(usuario=request.user, lida=False).update(lida=True)
    notificacoes = Notificacao.objects.filter(usuario=request.user)
    return render(request, 'notificacoes/lista_notificacoes.html', {'notificacoes': notificacoes})

@login_required
def deletar_notificacao(request, notificacao_id):
    # Utiliza get_object_or_404 para mais robustez
    notificacao = get_object_or_404(Notificacao, id=notificacao_id, usuario=request.user)
    notificacao.delete()
    messages.success(request, 'Notificação removida.') # Adiciona uma mensagem de sucesso
    return redirect('lista_notificacoes')

@login_required
def deletar_todas_notificacoes(request):
    if request.method == 'POST':
        Notificacao.objects.filter(usuario=request.user).delete()
        messages.success(request, 'Todas as notificações foram removidas com sucesso.')
    return redirect('lista_notificacoes')

@login_required
@require_POST
@csrf_exempt # O CSRF é tratado de outra forma em APIs PWA, mas para simplificar usamos exempt
def save_webpush_subscription(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        
        # Validação simples
        if 'endpoint' not in data or 'keys' not in data or 'p256dh' not in data['keys'] or 'auth' not in data['keys']:
            return JsonResponse({'error': 'Formato de inscrição inválido.'}, status=400)

        # Monta o objeto de inscrição
        subscription_data = {
            'endpoint': data['endpoint'],
            'p256dh': data['keys']['p256dh'],
            'auth': data['keys']['auth']
        }
        
        # Cria ou atualiza o dispositivo de push
        # A biblioteca django-webpush armazena isso no modelo WebPushDevice
        device, created = WebPushDevice.objects.get_or_create(
            user=request.user,
            browser=data.get('browser', 'UNKNOWN'), # Tentamos obter o browser, se o JS enviar
            registration_id=subscription_data['endpoint'],
            defaults={'p256dh': subscription_data['p256dh'], 'auth': subscription_data['auth']}
        )
        
        if not created:
            # Se já existia, atualiza as chaves (caso tenham mudado)
            device.p256dh = subscription_data['p256dh']
            device.auth = subscription_data['auth']
            device.save()
            
        return JsonResponse({'message': 'Inscrição salva com sucesso.'}, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Corpo da requisição inválido (JSON).'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
@require_POST
@csrf_exempt
def delete_webpush_subscription(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        endpoint = data.get('endpoint')
        
        if not endpoint:
            return JsonResponse({'error': 'Endpoint não fornecido.'}, status=400)
            
        # Deleta a inscrição baseada no endpoint e no usuário logado
        deleted_count, _ = WebPushDevice.objects.filter(
            user=request.user, 
            registration_id=endpoint
        ).delete()
        
        if deleted_count > 0:
            return JsonResponse({'message': 'Inscrição removida com sucesso.'}, status=200)
        else:
            return JsonResponse({'error': 'Inscrição não encontrada.'}, status=404)
            
    except Exception as e:
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
def get_vapid_public_key(request):
    # Envia a chave pública VAPID para o frontend
    public_key = settings.WEBPUSH_SETTINGS.get('VAPID_PUBLIC_KEY')
    if not public_key:
        return JsonResponse({'error': 'Chave VAPID pública não configurada no servidor.'}, status=500)
        
    return JsonResponse({'vapid_public_key': public_key})