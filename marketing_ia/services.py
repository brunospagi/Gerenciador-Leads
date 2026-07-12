import mimetypes

from django.core.files.base import ContentFile

from .ai_promocional import baixar_foto, gerar_imagem_promocional, gerar_legenda
from .models import PostPromocional, PreviewPost, VeiculoAnuncio
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


def gerar_post_para_anuncio(anuncio, usuario=None, lote=None):
    """
    Gera (foto com IA + legenda) para um único VeiculoAnuncio e salva
    diretamente um PostPromocional — usado pelo fluxo em lote ("gerar para
    todos"), que não passa por prévia manual item a item. Levanta
    GeracaoPostError com uma mensagem amigável em caso de falha esperada.
    """
    imagem_bytes, imagem_mime, modelo_imagem, prompt_usado, legenda, hashtags, modelo_texto = (
        _gerar_conteudo_promocional(anuncio)
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


def gerar_posts_em_lote(anuncios, usuario=None, lote=None):
    """
    Gera um post para cada anúncio da lista, tolerando falhas individuais
    (sem foto, IA indisponível etc) sem interromper o restante do lote.
    Retorna (gerados, falhas).
    """
    gerados, falhas = 0, 0
    for anuncio in anuncios:
        try:
            gerar_post_para_anuncio(anuncio, usuario=usuario, lote=lote)
            gerados += 1
        except GeracaoPostError:
            falhas += 1
    return gerados, falhas
