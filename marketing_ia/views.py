import io
import json
import threading
import time
from decimal import Decimal
from types import SimpleNamespace

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from configuracoes.access import require_module_action
from configuracoes.models import ConfiguracaoIntegracoes, WebhookIntegracao

from . import image_overlay
from .ai_promocional import baixar_foto
from .models import (
    EnvioWebhook, LayoutOverlay, LoteGeracao, PostCombinado, PostPromocional, PreviewPost, SincronizacaoEstoque,
    VeiculoAnuncio,
)
from .services import (
    GeracaoPostError, gerar_post_combinado, gerar_posts_em_lote, gerar_preview_post,
    salvar_preview_como_post, sincronizar_estoque, sugerir_grupos_combinados,
)
from .webhooks import enviar_post_combinado_webhook, enviar_post_webhook

# Espaço entre um disparo e outro no envio em massa (marketing_enviar_lote_webhook)
# — um post de cada vez, não tudo de uma rajada só, pra não sobrecarregar/
# atropelar o webhook receptor (ex: fluxo do n8n processando um de cada vez).
INTERVALO_ENVIO_LOTE_WEBHOOK_SEGUNDOS = 1.5


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
        gerados, falhas = gerar_posts_em_lote(
            anuncios, usuario=lote.iniciado_por, lote=lote,
            template_overlay=lote.template_overlay, resolucao_overlay=lote.resolucao_overlay,
        )
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


def _dado_filtro(request, campo):
    """GET na listagem, POST no disparo do lote — mesmos nomes de campo nos dois."""
    return request.GET.get(campo) or request.POST.get(campo)


def _aplicar_filtros_vantagens(queryset, request):
    """Filtros de vantagem (IPVA pago / Aceita troca / Veículo completo) usados
    tanto na listagem quanto no 'gerar para todos' — o mesmo seletor serve pra
    escolher o que aparece na tela e o que entra no lote."""
    tipo = _dado_filtro(request, 'tipo')
    if tipo in ('CARRO', 'MOTO'):
        queryset = queryset.filter(tipo=tipo)
    if _dado_filtro(request, 'ipva_pago'):
        queryset = queryset.filter(ipva_pago=True)
    if _dado_filtro(request, 'aceita_troca'):
        queryset = queryset.filter(aceita_troca=True)
    if _dado_filtro(request, 'veiculo_completo'):
        queryset = queryset.filter(veiculo_completo=True)
    return queryset


def _veiculos_para_lote(request):
    """Veículos candidatos ao lote de geração. Por padrão só entra quem ainda
    não tem post (evita recriar sem querer), mas o checkbox 'incluir_com_post'
    no modal permite incluir também quem já tem — pensado pra quem quer gerar
    posts pra todo o estoque regularmente, sem precisar descartar os antigos
    só pra poder gerar de novo."""
    queryset = VeiculoAnuncio.objects.filter(ativo=True)
    if not _dado_filtro(request, 'incluir_com_post'):
        queryset = queryset.filter(posts__isnull=True)
    return _aplicar_filtros_vantagens(queryset, request).distinct()


@require_module_action('marketing_ia', 'visualizar')
def veiculo_list(request):
    veiculos = _aplicar_filtros_vantagens(VeiculoAnuncio.objects.filter(ativo=True), request)

    sem_post = request.GET.get('sem_post')
    if sem_post:
        veiculos = veiculos.filter(posts__isnull=True)

    # annotate por último: evita contar errado quando o filtro "sem_post" acima
    # já usou um join na mesma relação 'posts'. order_by explícito porque
    # annotate+distinct faz o Django não confiar mais no Meta.ordering do
    # model pra paginação.
    veiculos = veiculos.distinct().annotate(num_posts=Count('posts')).order_by('-atualizado_em')

    paginator = Paginator(veiculos, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    # mesmos filtros (tipo/vantagens) aplicados no total do botão "gerar para
    # todos sem post", pra ele contar exatamente o que o seletor vai mandar pro lote.
    total_sem_post_filtrado = _aplicar_filtros_vantagens(
        VeiculoAnuncio.objects.filter(ativo=True, posts__isnull=True), request,
    ).distinct().count()

    config = ConfiguracaoIntegracoes.get_solo()
    template_choices = list(ConfiguracaoIntegracoes.TEMPLATE_IMAGEM_CHOICES) + [
        (layout.chave_template, f'Customizado: {layout.nome}') for layout in LayoutOverlay.objects.all()
    ]

    context = {
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'veiculos': page_obj,
        'sincronizacao': SincronizacaoEstoque.load(),
        'tipo_filtro': request.GET.get('tipo') or '',
        'sem_post_filtro': bool(sem_post),
        'ipva_pago_filtro': bool(request.GET.get('ipva_pago')),
        'aceita_troca_filtro': bool(request.GET.get('aceita_troca')),
        'veiculo_completo_filtro': bool(request.GET.get('veiculo_completo')),
        'total_anuncios': VeiculoAnuncio.objects.filter(ativo=True).count(),
        'total_posts': PostPromocional.objects.count(),
        'total_sem_post': total_sem_post_filtrado,
        'lote_em_andamento': LoteGeracao.objects.filter(status='RODANDO').order_by('-criado_em').first(),
        'ultimo_lote': LoteGeracao.objects.exclude(status='RODANDO').order_by('-criado_em').first(),
        'provedor_imagem_atual': config.provedor_imagem_ia,
        'provedor_imagem_choices': ConfiguracaoIntegracoes.PROVEDOR_IMAGEM_CHOICES,
        'template_imagem_overlay_choices': template_choices,
        'resolucao_imagem_overlay_choices': ConfiguracaoIntegracoes.RESOLUCAO_IMAGEM_CHOICES,
        'pode_trocar_provedor_imagem': (
            request.user.is_superuser
            or (hasattr(request.user, 'profile') and request.user.profile.nivel_acesso == 'ADMIN')
        ),
    }
    return render(request, 'marketing_ia/veiculo_list.html', context)


@require_module_action('marketing_ia', 'editar')
@require_POST
def atualizar_provedor_imagem(request):
    is_admin = request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.nivel_acesso == 'ADMIN'
    )
    if not is_admin:
        messages.error(request, 'Só administradores podem trocar o provedor de IA de imagem.')
        return redirect('marketing_veiculo_list')

    novo_provedor = request.POST.get('provedor_imagem_ia')
    if novo_provedor not in dict(ConfiguracaoIntegracoes.PROVEDOR_IMAGEM_CHOICES):
        messages.error(request, 'Provedor inválido.')
        return redirect('marketing_veiculo_list')

    config = ConfiguracaoIntegracoes.get_solo()
    config.provedor_imagem_ia = novo_provedor
    config.atualizado_por = request.user
    config.save(update_fields=['provedor_imagem_ia', 'atualizado_por', 'atualizado_em'])
    messages.success(request, f'IA de imagem trocada para "{config.get_provedor_imagem_ia_display()}".')
    return redirect('marketing_veiculo_list')


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


@require_module_action('marketing_ia', 'editar')
@require_POST
def cancelar_sincronizacao(request):
    """Destrava manualmente uma sincronização travada em 'RODANDO' (ex: o
    servidor reiniciou no meio da raspagem) sem precisar esperar o timeout
    automático de SincronizacaoEstoque.load()."""
    sync = SincronizacaoEstoque.load()
    if sync.status == 'RODANDO':
        sync.status = 'ERRO'
        sync.concluido_em = timezone.now()
        sync.resultado = 'Sincronização cancelada manualmente.'
        sync.save(update_fields=['status', 'concluido_em', 'resultado'])
        messages.success(request, 'Sincronização cancelada — pode iniciar uma nova.')
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
    config = ConfiguracaoIntegracoes.get_solo()
    template_choices = list(ConfiguracaoIntegracoes.TEMPLATE_IMAGEM_CHOICES) + [
        (layout.chave_template, f'Customizado: {layout.nome}') for layout in LayoutOverlay.objects.all()
    ]
    context = {
        'anuncio': anuncio,
        'posts': posts,
        'webhooks_ativos': WebhookIntegracao.objects.filter(ativo=True),
        'provedor_imagem_atual': config.provedor_imagem_ia,
        'template_imagem_overlay_choices': template_choices,
        'resolucao_imagem_overlay_choices': ConfiguracaoIntegracoes.RESOLUCAO_IMAGEM_CHOICES,
    }
    return render(request, 'marketing_ia/veiculo_detail.html', context)


@require_module_action('marketing_ia', 'criar')
@require_POST
def gerar_preview(request, pk):
    """Gera uma prévia (não grava no S3, só no banco) para o usuário conferir
    antes de publicar — a confirmação/descarte de fato acontecem em
    confirmar_preview/descartar_preview."""
    anuncio = get_object_or_404(VeiculoAnuncio, pk=pk)
    config = ConfiguracaoIntegracoes.get_solo()
    template_overlay = request.POST.get('template_overlay') or None
    resolucao_overlay = request.POST.get('resolucao_overlay') or None
    template_valido = template_overlay in dict(ConfiguracaoIntegracoes.TEMPLATE_IMAGEM_CHOICES) or (
        template_overlay and template_overlay.startswith('CUSTOM:')
        and LayoutOverlay.objects.filter(pk=template_overlay.split(':', 1)[1]).exists()
    )
    if not template_valido:
        template_overlay = None
    if resolucao_overlay not in dict(ConfiguracaoIntegracoes.RESOLUCAO_IMAGEM_CHOICES):
        resolucao_overlay = None

    try:
        preview = gerar_preview_post(
            anuncio, usuario=request.user,
            template_overlay=template_overlay, resolucao_overlay=resolucao_overlay,
        )
    except GeracaoPostError as exc:
        return JsonResponse({'ok': False, 'erro': str(exc)}, status=400)

    return JsonResponse({
        'ok': True,
        'preview_id': preview.pk,
        'imagem_url': reverse('marketing_preview_imagem', args=[preview.pk]),
        'legenda': preview.legenda,
        'hashtags': preview.hashtags,
        'modelo_ia_imagem': preview.modelo_ia_imagem,
        'mostrar_overlay_opcoes': config.provedor_imagem_ia == 'OVERLAY',
    })


@require_module_action('marketing_ia', 'visualizar')
def preview_imagem(request, preview_id):
    """Serve os bytes da imagem de uma prévia direto do banco (nunca vai pro S3
    até ser confirmada)."""
    preview = get_object_or_404(PreviewPost, pk=preview_id)
    return HttpResponse(bytes(preview.imagem_bytes), content_type=preview.imagem_mime_type)


@require_module_action('marketing_ia', 'criar')
@require_POST
def confirmar_preview(request, preview_id):
    """Publica a prévia: grava a imagem no S3 como PostPromocional de verdade
    e apaga a prévia."""
    preview = get_object_or_404(PreviewPost, pk=preview_id)
    anuncio_pk = preview.anuncio_id
    salvar_preview_como_post(preview)
    messages.success(request, 'Post promocional salvo com sucesso.')
    return redirect('marketing_veiculo_detail', pk=anuncio_pk)


@require_module_action('marketing_ia', 'criar')
@require_POST
def descartar_preview(request, preview_id):
    """Descarta a prévia sem nunca ter gravado nada no S3."""
    preview = get_object_or_404(PreviewPost, pk=preview_id)
    anuncio_pk = preview.anuncio_id
    preview.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('marketing_veiculo_detail', pk=anuncio_pk)


@require_module_action('marketing_ia', 'editar')
@require_POST
def post_atualizar_status(request, pk):
    post = get_object_or_404(PostPromocional, pk=pk)
    novo_status = request.POST.get('status')
    lote_id = post.lote_id
    anuncio_id = post.anuncio_id

    if novo_status not in dict(PostPromocional.STATUS_CHOICES):
        messages.error(request, 'Status inválido.')
    elif novo_status == 'DESCARTADO':
        # Descartar apaga o registro E o arquivo do storage (MinIO/S3) — só
        # marcar o status como DESCARTADO deixava a imagem pra sempre lá,
        # virando lixo sem nenhuma referência que a use.
        post.imagem.delete(save=False)
        post.delete()
        messages.success(request, 'Post descartado e imagem removida do armazenamento.')
    else:
        post.status = novo_status
        post.save(update_fields=['status'])
        messages.success(request, f'Post marcado como "{post.get_status_display()}".')

    if lote_id:
        return redirect('marketing_revisao_lote', lote_id=lote_id)
    return redirect('marketing_veiculo_detail', pk=anuncio_id)


@require_module_action('marketing_ia', 'visualizar')
def contar_lote(request):
    """Recalcula quantos veículos entrariam no lote com os filtros marcados no
    modal de 'Gerar para todos', pra mostrar a contagem em tempo real antes de
    confirmar (os mesmos filtros de request.GET usados na listagem)."""
    total = _veiculos_para_lote(request).count()
    return JsonResponse({'total': total})


@require_module_action('marketing_ia', 'criar')
@require_POST
def iniciar_geracao_lote(request):
    if LoteGeracao.objects.filter(status='RODANDO').exists():
        messages.warning(request, 'Já existe uma geração em lote em andamento.')
        return redirect('marketing_veiculo_list')

    anuncios = _veiculos_para_lote(request)
    ids = list(anuncios.values_list('pk', flat=True))
    if not ids:
        messages.warning(request, 'Não há veículos pra gerar com esses filtros.')
        return redirect('marketing_veiculo_list')

    config = ConfiguracaoIntegracoes.get_solo()
    template_overlay = request.POST.get('template_overlay') or None
    resolucao_overlay = request.POST.get('resolucao_overlay') or None
    template_valido = template_overlay in dict(ConfiguracaoIntegracoes.TEMPLATE_IMAGEM_CHOICES) or (
        template_overlay and template_overlay.startswith('CUSTOM:')
        and LayoutOverlay.objects.filter(pk=template_overlay.split(':', 1)[1]).exists()
    )
    if not template_valido:
        template_overlay = None
    if resolucao_overlay not in dict(ConfiguracaoIntegracoes.RESOLUCAO_IMAGEM_CHOICES):
        resolucao_overlay = None

    lote = LoteGeracao.objects.create(
        iniciado_por=request.user,
        alvo_ids=ids,
        total_alvo=len(ids),
        provedor_imagem_ia=config.provedor_imagem_ia,
        template_overlay=template_overlay,
        resolucao_overlay=resolucao_overlay,
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
def lote_list(request):
    """Histórico de todos os lotes já disparados — antes só dava pra ver o
    lote em andamento ou o último concluído, ficando impossível voltar num
    lote mais antigo pra revisar/enviar posts que ficaram pra trás."""
    lotes = LoteGeracao.objects.all().order_by('-criado_em')
    paginator = Paginator(lotes, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'lotes': page_obj,
    }
    return render(request, 'marketing_ia/lote_list.html', context)


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
def descartar_lote(request, lote_id):
    """Descarta de uma vez todos os posts do lote que ainda não foram
    publicados — cada um apaga sua imagem do storage (mesma limpeza do
    descarte individual), em vez de precisar clicar 'Descartar' post por
    post quando um lote inteiro saiu ruim."""
    lote = get_object_or_404(LoteGeracao, pk=lote_id)
    posts = lote.posts.exclude(status='PUBLICADO')
    total = posts.count()
    for post in posts:
        post.imagem.delete(save=False)
        post.delete()

    if not total:
        messages.warning(request, 'Não há posts pra descartar neste lote (todos já foram publicados).')
    else:
        messages.success(request, f'{total} post(s) descartado(s) e removido(s) do armazenamento.')
    return redirect('marketing_revisao_lote', lote_id=lote.pk)


def _enviar_lote_webhook_em_background(lote_id, webhook_id, usuario_id):
    """Dispara os posts do lote pro webhook um de cada vez, com uma pequena
    pausa entre um envio e outro (INTERVALO_ENVIO_LOTE_WEBHOOK_SEGUNDOS) —
    evita mandar tudo de uma rajada só, que podia sobrecarregar/atropelar o
    lado receptor (ex: workflow do n8n processando post por post). Roda em
    background pra não segurar a requisição pelo tempo total de todos os
    envios + pausas."""
    webhook = WebhookIntegracao.objects.filter(pk=webhook_id).first()
    if not webhook:
        return
    try:
        posts = list(LoteGeracao.objects.get(pk=lote_id).posts.exclude(status='DESCARTADO'))
        for indice, post in enumerate(posts):
            resultado = enviar_post_webhook(post, webhook)
            EnvioWebhook.objects.create(
                post=post,
                webhook=webhook,
                enviado_por_id=usuario_id,
                sucesso=resultado['sucesso'],
                status_code=resultado['status_code'],
                erro=resultado['erro'],
            )
            if indice < len(posts) - 1:
                time.sleep(INTERVALO_ENVIO_LOTE_WEBHOOK_SEGUNDOS)
    finally:
        connection.close()


@require_module_action('marketing_ia', 'editar')
@require_POST
def enviar_lote_webhook(request, lote_id):
    """Envia TODOS os posts do lote (exceto os descartados) pro webhook
    escolhido, um de cada vez (com pausa entre os disparos) em segundo
    plano, em vez de precisar clicar 'Enviar' post por post — pensado pro
    fluxo de 'gerar em massa e mandar tudo de uma vez'."""
    lote = get_object_or_404(LoteGeracao, pk=lote_id)
    webhook = get_object_or_404(WebhookIntegracao, pk=request.POST.get('webhook_id'), ativo=True)

    total = lote.posts.exclude(status='DESCARTADO').count()
    if not total:
        messages.warning(request, 'Não há posts pra enviar neste lote (todos foram descartados).')
        return redirect('marketing_revisao_lote', lote_id=lote.pk)

    thread = threading.Thread(
        target=_enviar_lote_webhook_em_background,
        args=(lote.pk, webhook.pk, request.user.pk),
        daemon=True,
    )
    thread.start()

    messages.success(
        request,
        f'Envio de {total} post(s) pro webhook "{webhook.nome}" iniciado em segundo plano, um de cada vez.',
    )
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


_ANUNCIO_EXEMPLO_LAYOUT = SimpleNamespace(
    marca='Toyota', modelo='Corolla', ano='2022', motorizacao='2.0',
    preco=Decimal('98500.00'),
)
_CHAMADA_EXEMPLO_LAYOUT = 'SUPER OFERTA'


def _foto_exemplo_layout():
    """Foto sintética (não depende de nenhum anúncio já cadastrado) só pra
    servir de fundo na prévia do editor de layout quando nenhum veículo com
    foto foi escolhido."""
    from PIL import Image, ImageDraw

    img = Image.new('RGB', (1600, 1067), color=(96, 116, 148))
    draw = ImageDraw.Draw(img)
    draw.rectangle([120, 480, 1480, 880], fill=(235, 235, 240))
    draw.ellipse([260, 800, 500, 980], fill=(20, 20, 20))
    draw.ellipse([1100, 800, 1340, 980], fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()


@require_module_action('marketing_ia', 'visualizar')
def layout_list(request):
    context = {
        'layouts': LayoutOverlay.objects.all(),
        'templates_fixos': ConfiguracaoIntegracoes.TEMPLATE_IMAGEM_CHOICES,
        'datas_comemorativas': image_overlay.DATA_COMEMORATIVA_CHOICES,
    }
    return render(request, 'marketing_ia/layout_list.html', context)


@require_module_action('marketing_ia', 'criar')
def layout_editor(request, pk=None):
    layout = get_object_or_404(LayoutOverlay, pk=pk) if pk else None
    elementos_iniciais = layout.elementos if layout else []

    base = request.GET.get('base')
    if not layout and base in image_overlay.ELEMENTOS_BASE:
        elementos_iniciais = image_overlay.ELEMENTOS_BASE[base]
    elif not layout and base in image_overlay.ELEMENTOS_DATAS_COMEMORATIVAS:
        elementos_iniciais = image_overlay.ELEMENTOS_DATAS_COMEMORATIVAS[base]

    context = {
        'layout': layout,
        'elementos_iniciais_json': json.dumps(elementos_iniciais),
        'veiculos_com_foto': (
            VeiculoAnuncio.objects.filter(ativo=True).exclude(foto_principal_url='').order_by('-atualizado_em')[:30]
        ),
        'resolucao_choices': ConfiguracaoIntegracoes.RESOLUCAO_IMAGEM_CHOICES,
        'fonte_choices': json.dumps(image_overlay.FONTE_CHOICES),
    }
    return render(request, 'marketing_ia/layout_editor.html', context)


@require_module_action('marketing_ia', 'criar')
@require_POST
def layout_salvar(request, pk=None):
    try:
        dados = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'ok': False, 'erro': 'JSON inválido.'}, status=400)

    nome = (dados.get('nome') or '').strip()
    elementos = dados.get('elementos')
    if not nome:
        return JsonResponse({'ok': False, 'erro': 'Dê um nome pro layout.'}, status=400)
    if not isinstance(elementos, list):
        return JsonResponse({'ok': False, 'erro': 'Elementos inválidos.'}, status=400)

    if pk:
        layout = get_object_or_404(LayoutOverlay, pk=pk)
        layout.nome = nome
        layout.elementos = elementos
        layout.save(update_fields=['nome', 'elementos', 'atualizado_em'])
    else:
        layout = LayoutOverlay.objects.create(nome=nome, elementos=elementos, criado_por=request.user)

    return JsonResponse({'ok': True, 'pk': layout.pk, 'chave_template': layout.chave_template})


@require_module_action('marketing_ia', 'editar')
@require_POST
def layout_excluir(request, pk):
    layout = get_object_or_404(LayoutOverlay, pk=pk)
    nome = layout.nome
    layout.delete()
    messages.success(request, f'Layout "{nome}" excluído.')
    return redirect('marketing_layout_list')


@require_module_action('marketing_ia', 'visualizar')
@require_POST
def layout_preview(request):
    """Renderiza (sem gravar nada em lugar nenhum) uma prévia do layout sendo
    editado — usa a foto de um anúncio real se indicado, ou uma foto de
    exemplo sintética, com dados fictícios de veículo, só pra mostrar
    visualmente onde cada elemento cai na imagem final."""
    try:
        dados = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'erro': 'JSON inválido.'}, status=400)

    elementos = dados.get('elementos')
    resolucao = dados.get('resolucao')
    anuncio_pk = dados.get('anuncio_pk')

    if not isinstance(elementos, list):
        return JsonResponse({'erro': 'Elementos inválidos.'}, status=400)

    anuncio = _ANUNCIO_EXEMPLO_LAYOUT
    foto_bytes = None
    if anuncio_pk:
        anuncio_real = VeiculoAnuncio.objects.filter(pk=anuncio_pk).first()
        if anuncio_real and (anuncio_real.foto_principal_url or anuncio_real.fotos_urls):
            anuncio = anuncio_real
            try:
                foto_bytes, _ = baixar_foto(anuncio_real.foto_principal_url or anuncio_real.fotos_urls[0])
            except Exception:
                foto_bytes = None

    if not foto_bytes:
        foto_bytes = _foto_exemplo_layout()

    try:
        imagem_bytes, mime_type = image_overlay.montar_imagem_layout(
            foto_bytes, anuncio, _CHAMADA_EXEMPLO_LAYOUT, elementos, resolucao=resolucao,
        )
    except image_overlay.ImageOverlayError as exc:
        return JsonResponse({'erro': str(exc)}, status=400)

    return HttpResponse(imagem_bytes, content_type=mime_type)


@require_module_action('marketing_ia', 'visualizar')
def combinados_list(request):
    """Tela de posts combinados (2 ou 4 veículos juntos numa colagem só):
    mostra grupos sugeridos automaticamente (por tipo ou marca, a partir do
    estoque que ainda não entrou em nenhum combinado) pra gerar com um clique,
    além dos combinados já gerados pra revisar/descartar/enviar."""
    quantidade = 4 if request.GET.get('quantidade') == '4' else 2
    criterio = request.GET.get('criterio') or 'MESMO_TIPO'
    if criterio not in dict(PostCombinado.CRITERIO_CHOICES):
        criterio = 'MESMO_TIPO'

    context = {
        'quantidade': quantidade,
        'criterio': criterio,
        'quantidade_choices': PostCombinado.QUANTIDADE_CHOICES,
        'criterio_choices': PostCombinado.CRITERIO_CHOICES,
        'grupos_sugeridos': sugerir_grupos_combinados(quantidade, criterio),
        'posts': PostCombinado.objects.prefetch_related('veiculos').all(),
        'webhooks_ativos': WebhookIntegracao.objects.filter(ativo=True),
    }
    return render(request, 'marketing_ia/combinados_list.html', context)


@require_module_action('marketing_ia', 'criar')
@require_POST
def gerar_combinado(request):
    ids = request.POST.getlist('veiculo_ids')
    criterio = request.POST.get('criterio') or 'MESMO_TIPO'
    if criterio not in dict(PostCombinado.CRITERIO_CHOICES):
        criterio = 'MESMO_TIPO'

    veiculos_por_id = {str(v.pk): v for v in VeiculoAnuncio.objects.filter(pk__in=ids)}
    # mantém a ordem em que os ids vieram do form (grupo já ordenado por
    # preço na sugestão) em vez da ordem arbitrária do queryset.
    veiculos = [veiculos_por_id[i] for i in ids if i in veiculos_por_id]

    if len(veiculos) not in (2, 4) or len(veiculos) != len(ids):
        messages.error(request, 'Selecione exatamente 2 ou 4 veículos válidos pra gerar o combinado.')
        return redirect('marketing_combinados_list')

    try:
        post = gerar_post_combinado(veiculos, criterio, usuario=request.user)
        messages.success(request, f'Post combinado com {post.quantidade} veículo(s) gerado com sucesso.')
    except GeracaoPostError as exc:
        messages.error(request, str(exc))
    return redirect('marketing_combinados_list')


@require_module_action('marketing_ia', 'editar')
@require_POST
def descartar_combinado(request, pk):
    post = get_object_or_404(PostCombinado, pk=pk)
    post.imagem.delete(save=False)
    post.delete()
    messages.success(request, 'Post combinado descartado e imagem removida do armazenamento.')
    return redirect('marketing_combinados_list')


@require_module_action('marketing_ia', 'editar')
@require_POST
def enviar_combinado_webhook_view(request, pk):
    post = get_object_or_404(PostCombinado, pk=pk)
    webhook = get_object_or_404(WebhookIntegracao, pk=request.POST.get('webhook_id'), ativo=True)
    resultado = enviar_post_combinado_webhook(post, webhook)
    if resultado['sucesso']:
        messages.success(request, f'Post combinado enviado para o webhook "{webhook.nome}".')
    else:
        messages.error(request, f'Falha ao enviar para "{webhook.nome}": {resultado["erro"]}')
    return redirect('marketing_combinados_list')
