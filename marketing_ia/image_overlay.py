"""
Monta a imagem promocional SEM IA de geração de imagem: usa a foto real do
veículo como está (só recorta, sem trocar cenário/fundo) e sobrepõe texto —
chamada curta (gerada pelo Gemini, só texto, sem custo de API de imagem) +
marca/modelo/ano + preço — desenhado com Pillow. Muito mais barato e rápido
que Leonardo/OpenAI/Gemini image-gen, ao custo de não poder trocar o
cenário da foto.

Inspirado em padrões comuns de posts de revenda de veículos (faixa de
info na parte de baixo, selo diagonal de oferta no canto, cartão
arredondado central) — layouts recorrentes em templates do setor
automotivo pra Instagram/Facebook.
"""
import io
import logging

from PIL import Image, ImageDraw, ImageFont, ImageOps

logger = logging.getLogger(__name__)

# Resoluções válidas pra redes sociais (Instagram/Facebook). Todas em 1080px
# de largura (padrão da plataforma) variando só a altura pro formato.
RESOLUCOES = {
    '1080x1080': (1080, 1080),   # feed quadrado (1:1)
    '1080x1350': (1080, 1350),   # feed retrato (4:5) — ocupa mais tela no app
    '1080x1920': (1080, 1920),   # stories / reels (9:16)
}
RESOLUCAO_PADRAO = '1080x1080'

COR_FAIXA = (15, 23, 42, 235)  # mesma cor escura da identidade M3 (--sidebar-bg / #0f172a)
COR_TEXTO_PRINCIPAL = (255, 255, 255, 255)
COR_TEXTO_PRECO = (74, 222, 128, 255)  # verde, destaca o preço na faixa escura
COR_CONTORNO = (0, 0, 0, 190)
COR_SELO_FUNDO = (197, 43, 48, 255)  # vermelho "oferta"

TEMPLATE_PADRAO = 'FAIXA_INFERIOR'


class ImageOverlayError(Exception):
    """Erro esperado ao montar a imagem com overlay (foto corrompida, etc)."""


def _fonte(tamanho):
    # Pillow >= 10.1 empacota uma fonte TrueType escalável (Aileron) acessível via
    # load_default(size=...) — não precisamos empacotar nenhum arquivo .ttf à parte.
    return ImageFont.load_default(size=max(int(tamanho), 10))


def _preparar_foto(foto_bytes, tamanho_saida):
    try:
        foto = Image.open(io.BytesIO(foto_bytes))
        foto = ImageOps.exif_transpose(foto)  # corrige rotação de fotos tiradas no celular
        foto = foto.convert('RGB')
    except Exception as exc:
        raise ImageOverlayError(f'Não foi possível abrir a foto original: {exc}') from exc
    return ImageOps.fit(foto, tamanho_saida, method=Image.LANCZOS)


def _formatar_preco(preco):
    if not preco:
        return 'Consulte o valor'
    return f"R$ {preco:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')


def _titulo_veiculo(anuncio):
    return f"{(anuncio.marca or '').upper()} {(anuncio.modelo or '').upper()} {anuncio.ano or ''}".strip()


def _quebrar_linhas(texto, fonte, draw, largura_max):
    """Quebra o texto em linhas que caibam em largura_max, medindo com a fonte real
    (textwrap sozinho só conta caracteres, não largura real renderizada)."""
    if not texto:
        return []
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


def _template_faixa_inferior(draw, largura, altura, anuncio, chamada):
    """Faixa escura full-width na parte de baixo, com chamada + título + preço
    empilhados — o layout mais comum em posts de revenda de veículo."""
    margem = int(largura * 0.06)
    largura_util = largura - (2 * margem)

    fonte_chamada = _fonte(largura * 0.062)
    fonte_titulo = _fonte(largura * 0.05)
    fonte_preco = _fonte(largura * 0.075)

    titulo = _titulo_veiculo(anuncio)
    linhas_titulo = _quebrar_linhas(titulo, fonte_titulo, draw, largura_util)
    linhas_chamada = _quebrar_linhas((chamada or '').upper(), fonte_chamada, draw, largura_util)

    espaco_chamada = int(fonte_chamada.size * 1.25)
    espaco_titulo = int(fonte_titulo.size * 1.25)
    espaco_preco = int(fonte_preco.size * 1.35)
    padding = int(largura * 0.05)

    altura_faixa = min(
        padding * 2 + len(linhas_chamada) * espaco_chamada + len(linhas_titulo) * espaco_titulo + espaco_preco,
        int(altura * 0.45),
    )

    draw.rectangle([(0, altura - altura_faixa), (largura, altura)], fill=COR_FAIXA)

    y = altura - altura_faixa + padding
    for linha in linhas_chamada:
        _texto_com_contorno(draw, (margem, y), linha, fonte_chamada, COR_TEXTO_PRINCIPAL)
        y += espaco_chamada
    for linha in linhas_titulo:
        _texto_com_contorno(draw, (margem, y), linha, fonte_titulo, COR_TEXTO_PRINCIPAL)
        y += espaco_titulo
    _texto_com_contorno(draw, (margem, y), _formatar_preco(anuncio.preco), fonte_preco, COR_TEXTO_PRECO)


def _selo_diagonal(overlay, texto, largura):
    """Cola uma faixa rotacionada (tipo adesivo de 'oferta') no canto superior
    esquerdo — desenha reto numa imagem à parte e rotaciona, porque o Pillow não
    tem uma primitiva de retângulo rotacionado direto no canvas principal."""
    faixa_l, faixa_a = int(largura * 0.9), int(largura * 0.14)
    faixa = Image.new('RGBA', (faixa_l, faixa_a), (0, 0, 0, 0))
    draw_faixa = ImageDraw.Draw(faixa)
    draw_faixa.rectangle([(0, 0), (faixa_l, faixa_a)], fill=COR_SELO_FUNDO)

    fonte = _fonte(faixa_a * 0.45)
    texto = (texto or '').upper()
    texto_w = draw_faixa.textlength(texto, font=fonte)
    draw_faixa.text(
        ((faixa_l - texto_w) / 2, faixa_a * 0.22), texto, font=fonte, fill=(255, 255, 255, 255),
    )

    faixa_rotada = faixa.rotate(-28, expand=True, resample=Image.BICUBIC)
    overlay.alpha_composite(
        faixa_rotada,
        (-int(faixa_rotada.width * 0.22), -int(faixa_rotada.height * 0.3)),
    )


def _template_selo_diagonal(overlay, draw, largura, altura, anuncio, chamada):
    """Selo diagonal de "oferta" no canto superior esquerdo (chamada) + faixa
    inferior compacta só com título e preço — comum em anúncios de "promoção"."""
    _selo_diagonal(overlay, chamada, largura)

    margem = int(largura * 0.06)
    largura_util = largura - (2 * margem)
    fonte_titulo = _fonte(largura * 0.05)
    fonte_preco = _fonte(largura * 0.08)

    titulo = _titulo_veiculo(anuncio)
    linhas_titulo = _quebrar_linhas(titulo, fonte_titulo, draw, largura_util)
    espaco_titulo = int(fonte_titulo.size * 1.25)
    espaco_preco = int(fonte_preco.size * 1.35)
    padding = int(largura * 0.05)

    altura_faixa = min(
        padding * 2 + len(linhas_titulo) * espaco_titulo + espaco_preco,
        int(altura * 0.32),
    )
    draw.rectangle([(0, altura - altura_faixa), (largura, altura)], fill=COR_FAIXA)

    y = altura - altura_faixa + padding
    for linha in linhas_titulo:
        _texto_com_contorno(draw, (margem, y), linha, fonte_titulo, COR_TEXTO_PRINCIPAL)
        y += espaco_titulo
    _texto_com_contorno(draw, (margem, y), _formatar_preco(anuncio.preco), fonte_preco, COR_TEXTO_PRECO)


def _template_cartao_central(draw, largura, altura, anuncio, chamada):
    """Cartão arredondado flutuante perto da base (com margem nas laterais, não
    edge-to-edge), estilo mais "app moderno" — chamada como pill no topo do
    cartão, título e preço abaixo."""
    margem_lateral = int(largura * 0.06)
    largura_cartao = largura - (2 * margem_lateral)

    fonte_chamada = _fonte(largura * 0.045)
    fonte_titulo = _fonte(largura * 0.052)
    fonte_preco = _fonte(largura * 0.075)

    padding = int(largura * 0.05)
    largura_util = largura_cartao - (2 * padding)

    titulo = _titulo_veiculo(anuncio)
    linhas_titulo = _quebrar_linhas(titulo, fonte_titulo, draw, largura_util)
    espaco_titulo = int(fonte_titulo.size * 1.25)
    espaco_preco = int(fonte_preco.size * 1.4)
    altura_pill = int(fonte_chamada.size * 1.9)

    altura_cartao = min(
        padding * 2 + altura_pill + len(linhas_titulo) * espaco_titulo + espaco_preco,
        int(altura * 0.42),
    )

    margem_inferior = int(altura * 0.05)
    topo_cartao = altura - altura_cartao - margem_inferior
    raio = int(largura * 0.04)

    draw.rounded_rectangle(
        [(margem_lateral, topo_cartao), (margem_lateral + largura_cartao, topo_cartao + altura_cartao)],
        radius=raio,
        fill=COR_FAIXA,
    )

    x = margem_lateral + padding
    y = topo_cartao + padding * 0.6

    if chamada:
        chamada_txt = chamada.upper()
        pill_largura = draw.textlength(chamada_txt, font=fonte_chamada) + int(largura * 0.06)
        draw.rounded_rectangle(
            [(x, y), (x + pill_largura, y + altura_pill)],
            radius=altura_pill / 2,
            fill=COR_SELO_FUNDO,
        )
        draw.text(
            (x + int(largura * 0.03), y + altura_pill * 0.18), chamada_txt,
            font=fonte_chamada, fill=(255, 255, 255, 255),
        )
        y += altura_pill * 1.3

    for linha in linhas_titulo:
        _texto_com_contorno(draw, (x, y), linha, fonte_titulo, COR_TEXTO_PRINCIPAL)
        y += espaco_titulo

    _texto_com_contorno(draw, (x, y), _formatar_preco(anuncio.preco), fonte_preco, COR_TEXTO_PRECO)


_TEMPLATES = {
    'FAIXA_INFERIOR': lambda overlay, draw, largura, altura, anuncio, chamada: _template_faixa_inferior(
        draw, largura, altura, anuncio, chamada,
    ),
    'SELO_DIAGONAL': lambda overlay, draw, largura, altura, anuncio, chamada: _template_selo_diagonal(
        overlay, draw, largura, altura, anuncio, chamada,
    ),
    'CARTAO_CENTRAL': lambda overlay, draw, largura, altura, anuncio, chamada: _template_cartao_central(
        draw, largura, altura, anuncio, chamada,
    ),
}


def montar_imagem_overlay(foto_bytes, anuncio, chamada, template=None, resolucao=None):
    """
    anuncio: VeiculoAnuncio (usa marca, modelo, ano, preco).
    chamada: frase curta e chamativa (gerada pelo Gemini em
    ai_promocional.gerar_chamada_ia, ou um fallback fixo).
    template: uma chave de _TEMPLATES (default: FAIXA_INFERIOR).
    resolucao: uma chave de RESOLUCOES (default: 1080x1080).
    Retorna (bytes, mime_type) ou levanta ImageOverlayError.
    """
    template = template if template in _TEMPLATES else TEMPLATE_PADRAO
    tamanho_saida = RESOLUCOES.get(resolucao, RESOLUCOES[RESOLUCAO_PADRAO])

    base = _preparar_foto(foto_bytes, tamanho_saida).convert('RGBA')
    largura, altura = base.size

    overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    _TEMPLATES[template](overlay, draw, largura, altura, anuncio, chamada)

    final = Image.alpha_composite(base, overlay).convert('RGB')
    saida = io.BytesIO()
    final.save(saida, format='JPEG', quality=90)
    return saida.getvalue(), 'image/jpeg'
