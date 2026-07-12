"""
Monta a imagem promocional SEM IA de geração de imagem: usa a foto real do
veículo como está (só recorta pra quadrado, sem trocar cenário/fundo) e
sobrepõe uma faixa com texto — chamada curta (gerada pelo Gemini, só texto,
sem custo de API de imagem) + marca/modelo/ano + preço — desenhada com
Pillow. Muito mais barato e rápido que Leonardo/OpenAI/Gemini image-gen,
ao custo de não poder trocar o cenário da foto.
"""
import io
import logging

from PIL import Image, ImageDraw, ImageFont, ImageOps

logger = logging.getLogger(__name__)

TAMANHO_SAIDA = (1080, 1080)
COR_FAIXA = (15, 23, 42, 235)  # mesma cor escura da identidade M3 (--sidebar-bg / #0f172a)
COR_TEXTO_PRINCIPAL = (255, 255, 255, 255)
COR_TEXTO_PRECO = (74, 222, 128, 255)  # verde, destaca o preço na faixa escura
COR_CONTORNO = (0, 0, 0, 190)


class ImageOverlayError(Exception):
    """Erro esperado ao montar a imagem com overlay (foto corrompida, etc)."""


def _fonte(tamanho):
    # Pillow >= 10.1 empacota uma fonte TrueType escalável (Aileron) acessível via
    # load_default(size=...) — não precisamos empacotar nenhum arquivo .ttf à parte.
    return ImageFont.load_default(size=tamanho)


def _preparar_foto_quadrada(foto_bytes):
    try:
        foto = Image.open(io.BytesIO(foto_bytes))
        foto = ImageOps.exif_transpose(foto)  # corrige rotação de fotos tiradas no celular
        foto = foto.convert('RGB')
    except Exception as exc:
        raise ImageOverlayError(f'Não foi possível abrir a foto original: {exc}') from exc
    return ImageOps.fit(foto, TAMANHO_SAIDA, method=Image.LANCZOS)


def _formatar_preco(preco):
    if not preco:
        return 'Consulte o valor'
    return f"R$ {preco:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')


def _quebrar_linhas(texto, fonte, draw, largura_max):
    """Quebra o texto em linhas que caibam em largura_max, medindo com a fonte real
    (textwrap sozinho só conta caracteres, não largura real renderizada)."""
    palavras = texto.split()
    linhas = []
    linha_atual = ''
    for palavra in palavras:
        candidata = f'{linha_atual} {palavra}'.strip()
        if draw.textlength(candidata, font=fonte) <= largura_max or not linha_atual:
            linha_atual = candidata
        else:
            linhas.append(linha_atual)
            linha_atual = palavra
    if linha_atual:
        linhas.append(linha_atual)
    return linhas


def _texto_com_contorno(draw, posicao, texto, fonte, cor_texto, espessura=2):
    x, y = posicao
    for dx in range(-espessura, espessura + 1):
        for dy in range(-espessura, espessura + 1):
            if dx or dy:
                draw.text((x + dx, y + dy), texto, font=fonte, fill=COR_CONTORNO)
    draw.text((x, y), texto, font=fonte, fill=cor_texto)


def montar_imagem_overlay(foto_bytes, anuncio, chamada):
    """
    anuncio: VeiculoAnuncio (usa marca, modelo, ano, preco).
    chamada: frase curta e chamativa pra destacar no topo da faixa (gerada
    pelo Gemini em ai_promocional.gerar_chamada_ia, ou um fallback fixo).
    Retorna (bytes, mime_type) ou levanta ImageOverlayError.
    """
    base = _preparar_foto_quadrada(foto_bytes).convert('RGBA')
    largura, altura = base.size
    margem = int(largura * 0.06)
    largura_util = largura - (2 * margem)

    overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    fonte_chamada = _fonte(max(int(largura * 0.062), 24))
    fonte_titulo = _fonte(max(int(largura * 0.05), 20))
    fonte_preco = _fonte(max(int(largura * 0.075), 28))

    titulo = f"{(anuncio.marca or '').upper()} {(anuncio.modelo or '').upper()} {anuncio.ano or ''}".strip()
    linhas_titulo = _quebrar_linhas(titulo, fonte_titulo, draw, largura_util) if titulo else []
    linhas_chamada = _quebrar_linhas((chamada or '').upper(), fonte_chamada, draw, largura_util)

    espaco_linha_chamada = int(fonte_chamada.size * 1.25)
    espaco_linha_titulo = int(fonte_titulo.size * 1.25)
    espaco_preco = int(fonte_preco.size * 1.35)
    padding_faixa = int(largura * 0.05)

    altura_faixa = (
        padding_faixa * 2
        + len(linhas_chamada) * espaco_linha_chamada
        + len(linhas_titulo) * espaco_linha_titulo
        + espaco_preco
    )
    altura_faixa = min(altura_faixa, int(altura * 0.45))

    draw.rectangle(
        [(0, altura - altura_faixa), (largura, altura)],
        fill=COR_FAIXA,
    )

    y = altura - altura_faixa + padding_faixa
    for linha in linhas_chamada:
        _texto_com_contorno(draw, (margem, y), linha, fonte_chamada, COR_TEXTO_PRINCIPAL)
        y += espaco_linha_chamada

    for linha in linhas_titulo:
        _texto_com_contorno(draw, (margem, y), linha, fonte_titulo, COR_TEXTO_PRINCIPAL)
        y += espaco_linha_titulo

    preco_txt = _formatar_preco(anuncio.preco)
    _texto_com_contorno(draw, (margem, y), preco_txt, fonte_preco, COR_TEXTO_PRECO)

    final = Image.alpha_composite(base, overlay).convert('RGB')
    saida = io.BytesIO()
    final.save(saida, format='JPEG', quality=90)
    return saida.getvalue(), 'image/jpeg'
