from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Notificacao
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from webpush.models import PushInformation  
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


# --- VIEWS PARA WEBPUSH (CORRIGIDAS) ---

@login_required
@require_POST
@csrf_exempt
def save_webpush_subscription(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        
        # Validação simples
        if 'endpoint' not in data:
            return JsonResponse({'error': 'Formato de inscrição inválido.'}, status=400)

        # Esta biblioteca salva a subscrição inteira como um JSON
        subscription_json = json.dumps(data)
        
        # CORREÇÃO: Usar o modelo PushInformation
        # A biblioteca espera que 'get_or_create' seja usado no 'subscription'
        device, created = PushInformation.objects.get_or_create(
            user=request.user,
            subscription=subscription_json,
            defaults={'browser': data.get('browser', 'UNKNOWN')}
        )
        
        if created:
            return JsonResponse({'message': 'Inscrição salva com sucesso.'}, status=201)
        else:
            return JsonResponse({'message': 'Inscrição já existia.'}, status=200)

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
            
        # CORREÇÃO: Temos que procurar pelo endpoint dentro do campo JSON 'subscription'
        deleted_count, _ = PushInformation.objects.filter(
            user=request.user, 
            subscription__contains=endpoint # Query correta
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