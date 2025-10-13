from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Notificacao

@login_required
def lista_notificacoes(request):
    # Marca todas as notificações como lidas ao acessar a página
    Notificacao.objects.filter(usuario=request.user, lida=False).update(lida=True)
    notificacoes = Notificacao.objects.filter(usuario=request.user)
    return render(request, 'notificacoes/lista_notificacoes.html', {'notificacoes': notificacoes})

@login_required
def deletar_notificacao(request, notificacao_id):
    notificacao = Notificacao.objects.get(id=notificacao_id, usuario=request.user)
    notificacao.delete()
    return redirect('lista_notificacoes')