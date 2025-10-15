from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Notificacao

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