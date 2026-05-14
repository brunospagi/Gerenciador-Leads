import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from webpush.models import PushInformation

from .models import Notificacao

logger = logging.getLogger(__name__)


@login_required
def lista_notificacoes(request):
    Notificacao.objects.filter(usuario=request.user, lida=False).update(lida=True)
    notificacoes = Notificacao.objects.filter(usuario=request.user)
    return render(request, 'notificacoes/lista_notificacoes.html', {'notificacoes': notificacoes})


@login_required
def deletar_notificacao(request, notificacao_id):
    notificacao = get_object_or_404(Notificacao, id=notificacao_id, usuario=request.user)
    notificacao.delete()
    messages.success(request, 'Notificacao removida.')
    return redirect('lista_notificacoes')


@login_required
def deletar_todas_notificacoes(request):
    if request.method == 'POST':
        Notificacao.objects.filter(usuario=request.user).delete()
        messages.success(request, 'Todas as notificacoes foram removidas com sucesso.')
    return redirect('lista_notificacoes')


@login_required
@require_POST
def save_webpush_subscription(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        endpoint = data.get('endpoint')
        if not endpoint:
            return JsonResponse({'error': 'Formato de inscricao invalido.'}, status=400)

        subscription_json = json.dumps(data)
        device, created = PushInformation.objects.get_or_create(
            user=request.user,
            subscription=subscription_json,
            defaults={'browser': data.get('browser', 'UNKNOWN')},
        )

        if created:
            return JsonResponse({'message': 'Inscricao salva com sucesso.'}, status=201)
        return JsonResponse({'message': 'Inscricao ja existia.'}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Corpo da requisicao invalido (JSON).'}, status=400)
    except Exception as exc:
        logger.exception('Erro ao salvar inscricao webpush: %s', exc)
        return JsonResponse({'error': 'Erro interno ao salvar inscricao.'}, status=500)


@login_required
@require_POST
def delete_webpush_subscription(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        endpoint = data.get('endpoint')

        if not endpoint:
            return JsonResponse({'error': 'Endpoint nao fornecido.'}, status=400)

        deleted_count, _ = PushInformation.objects.filter(
            user=request.user,
            subscription__contains=endpoint,
        ).delete()

        if deleted_count > 0:
            return JsonResponse({'message': 'Inscricao removida com sucesso.'}, status=200)
        return JsonResponse({'error': 'Inscricao nao encontrada.'}, status=404)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Corpo da requisicao invalido (JSON).'}, status=400)
    except Exception as exc:
        logger.exception('Erro ao remover inscricao webpush: %s', exc)
        return JsonResponse({'error': 'Erro interno ao remover inscricao.'}, status=500)


@login_required
def get_vapid_public_key(request):
    public_key = settings.WEBPUSH_SETTINGS.get('VAPID_PUBLIC_KEY')
    if not public_key:
        return JsonResponse({'error': 'Chave VAPID publica nao configurada no servidor.'}, status=500)

    return JsonResponse({'vapid_public_key': public_key})
