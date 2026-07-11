import threading

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from configuracoes.access import require_module_action
from configuracoes.models import WebhookIntegracao

from .models import EnvioWebhook, LoteGeracao, PostPromocional, SincronizacaoEstoque, VeiculoAnuncio
from .services import GeracaoPostError, gerar_post_para_anuncio, gerar_posts_em_lote, sincronizar_estoque
from .webhooks import enviar_post_webhook


def _executar_sincronizacao_em_background(sync_id):
    try:
        resultado = sincronizar_estoque()
        SincronizacaoEstoque.objects.filter(pk=sync_id).update(
            status='CONCLUIDO',
            concluido_em=timezone.now(),
            resultado=(
                f"{resultado['total']} anúncios no site — "
                f"{resultado['criados']} novo(s), {resultado['atualizados']} atualizado(s), "
                f"{resultado['desativados']} saiu(íram) do estoque."
            ),
        )
    except Exception as exc:
        SincronizacaoEstoque.objects.filter(pk=sync_id).update(
            status='ERRO',
            concluido_em=timezone.now(),
            resultado=f'Falha na sincronização: {exc}',
        )
    finally:
        connection.close()


def _executar_lote_em_background(lote_id):
    lote = LoteGeracao.objects.filter(pk=lote_id).first()
    if not lote:
        return
    try:
        anuncios = VeiculoAnuncio.objects.filter(pk__in=lote.alvo_ids)
        gerados, falhas = gerar_posts_em_lote(anuncios, usuario=lote.iniciado_por, lote=lote)
        lote.status = 'CONCLUIDO'
        lote.total_gerado = gerados
        lote.total_falhas = falhas
        lote.concluido_em = timezone.now()
        lote.save(update_fields=['status', 'total_gerado', 'total_falhas', 'concluido_em'])
    except Exception as exc:
        lote.status = 'ERRO'
        lote.erro = str(exc)
        lote.concluido_em = timezone.now()
        lote.save(update_fields=['status', 'erro', 'concluido_em'])
    finally:
        connection.close()


@require_module_action('marketing_ia', 'visualizar')
def veiculo_list(request):
    veiculos = VeiculoAnuncio.objects.filter(ativo=True)

    tipo = request.GET.get('tipo')
    if tipo in ('CARRO', 'MOTO'):
        veiculos = veiculos.filter(tipo=tipo)

    sem_post = request.GET.get('sem_post')
    if sem_post:
        veiculos = veiculos.filter(posts__isnull=True)

    # annotate por último: evita contar errado quando o filtro "sem_post" acima
    # já usou um join na mesma relação 'posts'.
    veiculos = veiculos.distinct().annotate(num_posts=Count('posts'))

    paginator = Paginator(veiculos, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'veiculos': page_obj,
        'sincronizacao': SincronizacaoEstoque.load(),
        'tipo_filtro': tipo or '',
        'sem_post_filtro': bool(sem_post),
        'total_anuncios': VeiculoAnuncio.objects.filter(ativo=True).count(),
        'total_posts': PostPromocional.objects.count(),
        'total_sem_post': VeiculoAnuncio.objects.filter(ativo=True, posts__isnull=True).distinct().count(),
        'lote_em_andamento': LoteGeracao.objects.filter(status='RODANDO').order_by('-criado_em').first(),
        'ultimo_lote': LoteGeracao.objects.exclude(status='RODANDO').order_by('-criado_em').first(),
    }
    return render(request, 'marketing_ia/veiculo_list.html', context)


@require_module_action('marketing_ia', 'criar')
@require_POST
def iniciar_sincronizacao(request):
    sync = SincronizacaoEstoque.load()
    if sync.status == 'RODANDO':
        messages.warning(request, 'Já existe uma sincronização em andamento.')
        return redirect('marketing_veiculo_list')

    sync.status = 'RODANDO'
    sync.iniciado_por = request.user
    sync.iniciado_em = timezone.now()
    sync.concluido_em = None
    sync.resultado = ''
    sync.save()

    thread = threading.Thread(target=_executar_sincronizacao_em_background, args=(sync.pk,), daemon=True)
    thread.start()

    messages.success(request, 'Sincronização com o site iniciada em segundo plano. Isso pode levar alguns minutos.')
    return redirect('marketing_veiculo_list')


@require_module_action('marketing_ia', 'visualizar')
def status_sincronizacao(request):
    sync = SincronizacaoEstoque.load()
    return JsonResponse({
        'status': sync.status,
        'resultado': sync.resultado,
        'iniciado_em': sync.iniciado_em.isoformat() if sync.iniciado_em else None,
        'concluido_em': sync.concluido_em.isoformat() if sync.concluido_em else None,
    })


@require_module_action('marketing_ia', 'visualizar')
def veiculo_detail(request, pk):
    anuncio = get_object_or_404(VeiculoAnuncio, pk=pk)
    posts = anuncio.posts.order_by('-gerado_em')
    context = {
        'anuncio': anuncio,
        'posts': posts,
        'webhooks_ativos': WebhookIntegracao.objects.filter(ativo=True),
    }
    return render(request, 'marketing_ia/veiculo_detail.html', context)


@require_module_action('marketing_ia', 'criar')
@require_POST
def gerar_post(request, pk):
    anuncio = get_object_or_404(VeiculoAnuncio, pk=pk)
    try:
        gerar_post_para_anuncio(anuncio, usuario=request.user)
        messages.success(request, f'Post promocional gerado para "{anuncio.titulo}".')
    except GeracaoPostError as exc:
        messages.error(request, str(exc))
    return redirect('marketing_veiculo_detail', pk=anuncio.pk)


@require_module_action('marketing_ia', 'editar')
@require_POST
def post_atualizar_status(request, pk):
    post = get_object_or_404(PostPromocional, pk=pk)
    novo_status = request.POST.get('status')
    if novo_status not in dict(PostPromocional.STATUS_CHOICES):
        messages.error(request, 'Status inválido.')
    else:
        post.status = novo_status
        post.save(update_fields=['status'])
        messages.success(request, f'Post marcado como "{post.get_status_display()}".')

    if post.lote_id:
        return redirect('marketing_revisao_lote', lote_id=post.lote_id)
    return redirect('marketing_veiculo_detail', pk=post.anuncio_id)


@require_module_action('marketing_ia', 'criar')
@require_POST
def iniciar_geracao_lote(request):
    if LoteGeracao.objects.filter(status='RODANDO').exists():
        messages.warning(request, 'Já existe uma geração em lote em andamento.')
        return redirect('marketing_veiculo_list')

    anuncios = VeiculoAnuncio.objects.filter(ativo=True, posts__isnull=True).distinct()
    ids = list(anuncios.values_list('pk', flat=True))
    if not ids:
        messages.warning(request, 'Não há veículos sem post para gerar.')
        return redirect('marketing_veiculo_list')

    lote = LoteGeracao.objects.create(
        iniciado_por=request.user,
        alvo_ids=ids,
        total_alvo=len(ids),
    )

    thread = threading.Thread(target=_executar_lote_em_background, args=(lote.pk,), daemon=True)
    thread.start()

    messages.success(
        request,
        f'Geração em lote iniciada para {len(ids)} veículo(s) em segundo plano. Isso pode levar alguns minutos.',
    )
    return redirect('marketing_veiculo_list')


@require_module_action('marketing_ia', 'visualizar')
def status_lote(request, lote_id):
    lote = get_object_or_404(LoteGeracao, pk=lote_id)
    return JsonResponse({
        'status': lote.status,
        'total_alvo': lote.total_alvo,
        'total_gerado': lote.total_gerado,
        'total_falhas': lote.total_falhas,
        'erro': lote.erro,
    })


@require_module_action('marketing_ia', 'visualizar')
def revisao_lote(request, lote_id):
    lote = get_object_or_404(LoteGeracao, pk=lote_id)
    posts = lote.posts.select_related('anuncio').order_by('-gerado_em')
    context = {
        'lote': lote,
        'posts': posts,
        'webhooks_ativos': WebhookIntegracao.objects.filter(ativo=True),
    }
    return render(request, 'marketing_ia/revisao_lote.html', context)


@require_module_action('marketing_ia', 'editar')
@require_POST
def aprovar_lote(request, lote_id):
    lote = get_object_or_404(LoteGeracao, pk=lote_id)
    total = lote.posts.filter(status='RASCUNHO').update(status='APROVADO')
    messages.success(request, f'{total} post(s) aprovado(s) e prontos para publicar.')
    return redirect('marketing_revisao_lote', lote_id=lote.pk)


@require_module_action('marketing_ia', 'editar')
@require_POST
def enviar_post_webhook_view(request, pk):
    post = get_object_or_404(PostPromocional, pk=pk)
    webhook = get_object_or_404(WebhookIntegracao, pk=request.POST.get('webhook_id'), ativo=True)

    resultado = enviar_post_webhook(post, webhook)
    EnvioWebhook.objects.create(
        post=post,
        webhook=webhook,
        enviado_por=request.user,
        sucesso=resultado['sucesso'],
        status_code=resultado['status_code'],
        erro=resultado['erro'],
    )

    if resultado['sucesso']:
        messages.success(request, f'Post enviado para o webhook "{webhook.nome}".')
    else:
        messages.error(request, f'Falha ao enviar para "{webhook.nome}": {resultado["erro"]}')

    if post.lote_id:
        return redirect('marketing_revisao_lote', lote_id=post.lote_id)
    return redirect('marketing_veiculo_detail', pk=post.anuncio_id)
