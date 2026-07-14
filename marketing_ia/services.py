import mimetypes
import random

from django.core.files.base import ContentFile

from . import image_overlay
from .ai_promocional import baixar_foto, gerar_imagem_promocional, gerar_legenda
from .models import PostCombinado, PostPromocional, PreviewPost, VeiculoAnuncio
from .scraping import scrape_estoque


class GeracaoPostError(Exception):
    """Erro esperado ao gerar um post promocional (sem foto, falha na IA, etc)."""


def sincronizar_estoque(max_paginas=None, tipo=None, limit=None):
    """
    Raspa o estoque público do site e sincroniza com VeiculoAnuncio.
    Retorna um dict com contadores: criados, atualizados, desativados, total.
    """
    anuncios_raspados = scrape_estoque(max_paginas=max_paginas, tipo=tipo, limit=limit)

    ids_encontrados = []
    criados, atualizados = 0, 0
    for dados in anuncios_raspados:
        if not dados.get('external_id'):
            continue
        ids_encontrados.append(dados['external_id'])
        _, foi_criado = VeiculoAnuncio.objects.update_or_create(
            external_id=dados['external_id'],
            defaults={
                'url': dados['url'],
                'tipo': dados['tipo'],
                'marca': dados['marca'],
                'modelo': dados['modelo'],
                'titulo': dados['titulo'],
                'preco': dados['preco'],
                'ano': dados['ano'],
                'km': dados['km'],
                'cor': dados['cor'],
                'cambio': dados['cambio'],
                'combustivel': dados['combustivel'],
                'carroceria': dados['carroceria'],
                'portas': dados['portas'],
                'motorizacao': dados['motorizacao'],
                'condicoes': dados['condicoes'],
                'ipva_pago': dados['ipva_pago'],
                'aceita_troca': dados['aceita_troca'],
                'veiculo_completo': dados['veiculo_completo'],
                'opcionais': dados['opcionais'],
                'descricao': dados['descricao'],
                'foto_principal_url': dados['foto_principal_url'],
                'fotos_urls': dados['fotos_urls'],
                'ativo': True,
            },
        )
        criados += int(foi_criado)
        atualizados += int(not foi_criado)

    desativados = 0
    # Só reconcilia "saiu do estoque" quando a raspagem cobriu o catálogo inteiro
    # (sem limites de página/quantidade), senão marcaria como inativo por engano.
    if ids_encontrados and not limit and not max_paginas:
        desativados = (
            VeiculoAnuncio.objects
            .filter(ativo=True)
            .exclude(external_id__in=ids_encontrados)
            .update(ativo=False)
        )

    return {
        'total': len(ids_encontrados),
        'criados': criados,
        'atualizados': atualizados,
        'desativados': desativados,
    }


def _gerar_conteudo_promocional(anuncio, template_overlay=None, resolucao_overlay=None):
    """Baixa a foto original e gera (imagem + legenda) via IA. Não grava nada —
    usado tanto pela geração direta em lote quanto pela prévia manual."""
    if not anuncio.fotos_urls:
        raise GeracaoPostError('Este anúncio não tem fotos para usar como referência.')

    try:
        foto_bytes, mime_type = baixar_foto(anuncio.foto_principal_url or anuncio.fotos_urls[0])
    except Exception as exc:
        raise GeracaoPostError(f'Falha ao baixar a foto original: {exc}') from exc

    imagem_bytes, imagem_mime, modelo_imagem, prompt_usado = gerar_imagem_promocional(
        anuncio, foto_bytes, mime_type, template_overlay=template_overlay, resolucao_overlay=resolucao_overlay,
    )
    if not imagem_bytes:
        raise GeracaoPostError('A IA não conseguiu gerar a imagem promocional. Tente novamente em instantes.')

    legenda, hashtags, modelo_texto = gerar_legenda(anuncio)
    if not legenda:
        legenda = anuncio.titulo
        hashtags = ''

    return imagem_bytes, imagem_mime, modelo_imagem, prompt_usado, legenda, hashtags, modelo_texto


def gerar_post_para_anuncio(anuncio, usuario=None, lote=None, template_overlay=None, resolucao_overlay=None):
    """
    Gera (foto com IA + legenda) para um único VeiculoAnuncio e salva
    diretamente um PostPromocional — usado pelo fluxo em lote ("gerar para
    todos"), que não passa por prévia manual item a item. Levanta
    GeracaoPostError com uma mensagem amigável em caso de falha esperada.
    """
    imagem_bytes, imagem_mime, modelo_imagem, prompt_usado, legenda, hashtags, modelo_texto = (
        _gerar_conteudo_promocional(anuncio, template_overlay=template_overlay, resolucao_overlay=resolucao_overlay)
    )

    extensao = mimetypes.guess_extension(imagem_mime) or '.png'
    post = PostPromocional(
        anuncio=anuncio,
        lote=lote,
        legenda=legenda,
        hashtags=hashtags or '',
        prompt_imagem=prompt_usado or '',
        modelo_ia_imagem=modelo_imagem,
        modelo_ia_texto=modelo_texto,
        gerado_por=usuario,
    )
    post.imagem.save(f'post{extensao}', ContentFile(imagem_bytes), save=False)
    post.save()
    return post


def gerar_preview_post(anuncio, usuario=None, template_overlay=None, resolucao_overlay=None):
    """
    Gera (foto com IA + legenda) e salva como PreviewPost (só no banco, sem
    gravar no S3) para o usuário conferir antes de publicar de verdade.
    Levanta GeracaoPostError em caso de falha esperada.
    """
    imagem_bytes, imagem_mime, modelo_imagem, prompt_usado, legenda, hashtags, modelo_texto = (
        _gerar_conteudo_promocional(anuncio, template_overlay=template_overlay, resolucao_overlay=resolucao_overlay)
    )

    return PreviewPost.objects.create(
        anuncio=anuncio,
        imagem_bytes=imagem_bytes,
        imagem_mime_type=imagem_mime,
        legenda=legenda,
        hashtags=hashtags or '',
        prompt_imagem=prompt_usado or '',
        modelo_ia_imagem=modelo_imagem,
        modelo_ia_texto=modelo_texto,
        gerado_por=usuario,
    )


def salvar_preview_como_post(preview, lote=None):
    """Confirma uma PreviewPost: grava a imagem no S3 como PostPromocional de
    verdade e apaga a prévia (o banco não guarda as duas cópias)."""
    extensao = mimetypes.guess_extension(preview.imagem_mime_type) or '.jpg'
    post = PostPromocional(
        anuncio=preview.anuncio,
        lote=lote,
        legenda=preview.legenda,
        hashtags=preview.hashtags or '',
        prompt_imagem=preview.prompt_imagem or '',
        modelo_ia_imagem=preview.modelo_ia_imagem,
        modelo_ia_texto=preview.modelo_ia_texto,
        gerado_por=preview.gerado_por,
    )
    post.imagem.save(f'post{extensao}', ContentFile(bytes(preview.imagem_bytes)), save=False)
    post.save()
    preview.delete()
    return post


def gerar_posts_em_lote(anuncios, usuario=None, lote=None, template_overlay=None, resolucao_overlay=None):
    """
    Gera um post para cada anúncio da lista, tolerando falhas individuais
    (sem foto, IA indisponível etc) sem interromper o restante do lote.
    Retorna (gerados, falhas).
    """
    gerados, falhas = 0, 0
    for anuncio in anuncios:
        try:
            gerar_post_para_anuncio(
                anuncio, usuario=usuario, lote=lote,
                template_overlay=template_overlay, resolucao_overlay=resolucao_overlay,
            )
            gerados += 1
        except GeracaoPostError:
            falhas += 1
    return gerados, falhas


def _campo_agrupamento(criterio):
    return 'marca' if criterio == 'MESMA_MARCA' else 'tipo'


def sugerir_grupos_combinados(quantidade, criterio='MESMO_TIPO'):
    """
    Sugere grupos de `quantidade` (2 ou 4) veículos ativos, com foto, que
    ainda não entraram em nenhum post combinado — agrupados por tipo ou marca
    (critério) e fatiados em blocos de `quantidade`, ordenados por preço (pra
    juntar veículos de faixa parecida no mesmo post). Não persiste nada, só
    devolve as sugestões pra tela confirmar/gerar. Feito em memória (em vez de
    filtro de JSONField no banco) porque fotos_urls/foto_principal_url variam
    entre os backends de banco suportados (sqlite nos testes, produção real).
    """
    campo = _campo_agrupamento(criterio)
    ids_ja_combinados = VeiculoAnuncio.objects.filter(posts_combinados__isnull=False).values_list('pk', flat=True)
    candidatos = list(
        VeiculoAnuncio.objects.filter(ativo=True)
        .exclude(pk__in=ids_ja_combinados)
        .order_by(campo, 'preco')
    )
    candidatos = [v for v in candidatos if v.foto_principal_url or v.fotos_urls]

    por_chave = {}
    for veiculo in candidatos:
        chave = (getattr(veiculo, campo) or '').strip()
        if not chave:
            continue
        por_chave.setdefault(chave, []).append(veiculo)

    grupos = []
    for veiculos in por_chave.values():
        limite = len(veiculos) - (len(veiculos) % quantidade)
        for i in range(0, limite, quantidade):
            grupos.append(veiculos[i:i + quantidade])
    return grupos


def _montar_legenda_combinada(veiculos, chamada):
    """Legenda determinística (sem IA — o post combinado usa só Pillow,
    mesma filosofia de custo zero do provedor OVERLAY): uma linha de chamada
    + uma linha por veículo com modelo e preço, já que o rótulo individual
    por veículo é o padrão em posts reais de comparação/lineup."""
    linhas = [f'{chamada}! 🚗', '']
    for veiculo in veiculos:
        titulo = image_overlay._titulo_veiculo(veiculo)
        preco = image_overlay._formatar_preco(veiculo.preco)
        linhas.append(f'• {titulo} — {preco}')
    linhas.append('')
    linhas.append('Fale com a gente e agende uma visita! 📲')
    legenda = '\n'.join(linhas)
    hashtags = '#carrosseminovos #revendadeveiculos #ofertas'
    return legenda, hashtags


def gerar_post_combinado(veiculos, criterio, usuario=None):
    """
    Baixa a foto principal de cada veículo do grupo (2 ou 4) e monta uma
    única imagem em grade (image_overlay.montar_imagem_grid), sem IA de
    geração de imagem. Levanta GeracaoPostError em caso de falha esperada
    (veículo sem foto, download falhou etc) — nenhum veículo é salvo se
    algum do grupo falhar, pra não gerar um combinado pela metade.
    """
    quantidade = len(veiculos)
    if quantidade not in (2, 4):
        raise GeracaoPostError('É preciso exatamente 2 ou 4 veículos pra gerar um post combinado.')

    fotos_bytes = []
    for veiculo in veiculos:
        url_foto = veiculo.foto_principal_url or (veiculo.fotos_urls[0] if veiculo.fotos_urls else None)
        if not url_foto:
            raise GeracaoPostError(f'O veículo "{veiculo.titulo}" não tem foto para usar no combinado.')
        try:
            foto_bytes, _ = baixar_foto(url_foto)
        except Exception as exc:
            raise GeracaoPostError(f'Falha ao baixar a foto de "{veiculo.titulo}": {exc}') from exc
        fotos_bytes.append(foto_bytes)

    chamada = random.choice(image_overlay.CHAMADAS_COMBINADO)
    try:
        imagem_bytes, imagem_mime = image_overlay.montar_imagem_grid(fotos_bytes, veiculos, chamada)
    except image_overlay.ImageOverlayError as exc:
        raise GeracaoPostError(str(exc)) from exc

    legenda, hashtags = _montar_legenda_combinada(veiculos, chamada)

    extensao = mimetypes.guess_extension(imagem_mime) or '.jpg'
    post = PostCombinado(quantidade=quantidade, criterio=criterio, legenda=legenda, hashtags=hashtags, gerado_por=usuario)
    post.imagem.save(f'combinado{extensao}', ContentFile(imagem_bytes), save=False)
    post.save()
    post.veiculos.set(veiculos)
    return post
