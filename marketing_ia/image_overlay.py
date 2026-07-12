"""
Monta a imagem promocional SEM IA de geração de imagem: usa a foto real do
veículo como está, sem cortar nada dela (encaixa inteira dentro do quadro,
com fundo desfocado preenchendo a sobra), e sobrepõe texto — chamada curta
(gerada pelo Gemini, só texto, sem custo de API de imagem) + marca/modelo/ano
+ preço + logo da Spagi Motors — desenhado com Pillow. Muito mais barato e
rápido que Leonardo/OpenAI/Gemini image-gen, ao custo de não poder trocar o
cenário da foto.

Inspirado em padrões comuns de posts de revenda de veículos (faixa de
info na parte de baixo, selo diagonal de oferta no canto, cartão
arredondado central) — layouts recorrentes em templates do setor
automotivo pra Instagram/Facebook.
"""
import io
import logging
import math

from django.conf import settings
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

logger = logging.getLogger(__name__)

LOGO_PATH = settings.BASE_DIR / 'static' / 'images' / 'logo-spagi-motors.webp'
_logo_cache = None

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
    """Encaixa a foto inteira dentro do quadro sem cortar nada do veículo — quando a
    proporção da foto não bate com a da rede social, sobra espaço nas laterais/topo,
    preenchido com a própria foto ampliada e borrada ao fundo (em vez de tarjas
    sólidas), técnica comum em stories/posts pra foto que não é nativamente 9:16/1:1."""
    try:
        foto = Image.open(io.BytesIO(foto_bytes))
        foto = ImageOps.exif_transpose(foto)  # corrige rotação de fotos tiradas no celular
        foto = foto.convert('RGB')
    except Exception as exc:
        raise ImageOverlayError(f'Não foi possível abrir a foto original: {exc}') from exc

    fundo = ImageOps.fit(foto, tamanho_saida, method=Image.LANCZOS)
    fundo = fundo.filter(ImageFilter.GaussianBlur(tamanho_saida[0] * 0.03))
    fundo = ImageEnhance.Brightness(fundo).enhance(0.55)

    foto_contida = ImageOps.contain(foto, tamanho_saida, method=Image.LANCZOS)
    pos = ((tamanho_saida[0] - foto_contida.width) // 2, (tamanho_saida[1] - foto_contida.height) // 2)
    fundo.paste(foto_contida, pos)
    return fundo


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


def _carregar_logo():
    """Carrega o wordmark da Spagi Motors (fundo transparente, texto branco/laranja —
    pensado pra ficar sobre as faixas/cartões escuros dos templates) uma única vez
    por processo."""
    global _logo_cache
    if _logo_cache is None:
        try:
            _logo_cache = Image.open(LOGO_PATH).convert('RGBA')
        except Exception as exc:
            logger.warning('Não foi possível carregar o logo da Spagi Motors: %s', exc)
            _logo_cache = False
    return _logo_cache or None


def _colar_logo(overlay, largura, x_direita, y_topo, altura_disponivel):
    """Cola o logo no canto superior direito da faixa/cartão escuro passado. O
    tamanho é proporcional à LARGURA da imagem (não à altura da faixa) — faixas
    mais altas (ex: chamada + título + preço empilhados) não devem inflar o
    logo, só a pill pequena da chamada teria menos espaço, por isso o teto de
    60% da altura disponível como segurança."""
    logo = _carregar_logo()
    if logo is None:
        return
    altura_logo = max(min(int(largura * 0.085), int(altura_disponivel * 0.6)), 1)
    largura_logo = max(int(logo.width * (altura_logo / logo.height)), 1)
    logo_redimensionado = logo.resize((largura_logo, altura_logo), Image.LANCZOS)
    margem = int(largura * 0.03)
    pos = (x_direita - largura_logo - margem, y_topo + margem)
    overlay.alpha_composite(logo_redimensionado, pos)


def _texto_com_contorno(draw, posicao, texto, fonte, cor_texto, espessura=2):
    x, y = posicao
    for dx in range(-espessura, espessura + 1):
        for dy in range(-espessura, espessura + 1):
            if dx or dy:
                draw.text((x + dx, y + dy), texto, font=fonte, fill=COR_CONTORNO)
    draw.text((x, y), texto, font=fonte, fill=cor_texto)


def _template_faixa_inferior(overlay, draw, largura, altura, anuncio, chamada):
    """Faixa escura full-width na parte de baixo, com chamada + título + preço
    empilhados — o layout mais comum em posts de revenda de veículo."""
    margem = int(largura * 0.06)
    largura_util = largura - (2 * margem)
    # a chamada é a única linha que sempre cai na mesma altura do logo (canto
    # superior direito da faixa) — reserva espaço só pra ela, título e preço
    # continuam usando a largura toda.
    largura_util_chamada = largura_util - int(largura * 0.27)

    fonte_chamada = _fonte(largura * 0.062)
    fonte_titulo = _fonte(largura * 0.05)
    fonte_preco = _fonte(largura * 0.075)

    titulo = _titulo_veiculo(anuncio)
    linhas_titulo = _quebrar_linhas(titulo, fonte_titulo, draw, largura_util)
    linhas_chamada = _quebrar_linhas((chamada or '').upper(), fonte_chamada, draw, largura_util_chamada)

    espaco_chamada = int(fonte_chamada.size * 1.25)
    espaco_titulo = int(fonte_titulo.size * 1.25)
    espaco_preco = int(fonte_preco.size * 1.35)
    padding = int(largura * 0.05)

    altura_faixa = min(
        padding * 2 + len(linhas_chamada) * espaco_chamada + len(linhas_titulo) * espaco_titulo + espaco_preco,
        int(altura * 0.45),
    )

    draw.rectangle([(0, altura - altura_faixa), (largura, altura)], fill=COR_FAIXA)
    _colar_logo(overlay, largura, largura, altura - altura_faixa, altura_faixa)

    y = altura - altura_faixa + padding
    for linha in linhas_chamada:
        _texto_com_contorno(draw, (margem, y), linha, fonte_chamada, COR_TEXTO_PRINCIPAL)
        y += espaco_chamada
    for linha in linhas_titulo:
        _texto_com_contorno(draw, (margem, y), linha, fonte_titulo, COR_TEXTO_PRINCIPAL)
        y += espaco_titulo
    _texto_com_contorno(draw, (margem, y), _formatar_preco(anuncio.preco), fonte_preco, COR_TEXTO_PRECO)


def _selo_diagonal(overlay, texto, largura, altura):
    """Desenha uma faixa diagonal (tipo adesivo de 'oferta') atravessando o canto
    superior esquerdo. Em vez de rotacionar uma imagem à parte e reposicionar por
    tentativa e erro (o que cortava o texto — as contas de onde o canto acabava
    indo parar depois do rotate()+expand não fecham de cabeça), calcula os 4
    cantos do paralelogramo já rotacionados em torno do centro do texto: assim
    a faixa e o texto usam exatamente o mesmo centro de rotação, garantido
    dentro do quadro, e só as pontas (sem texto, com padding de sobra) podem
    sair da área visível."""
    angulo_graus = -28
    rad = math.radians(angulo_graus)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    fonte = _fonte(largura * 0.052)
    texto = (texto or '').upper()

    faixa_a = int(largura * 0.13)
    medidor = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    texto_w = medidor.textlength(texto, font=fonte)
    padding_ponta = faixa_a * 1.3
    faixa_l = texto_w + 2 * padding_ponta

    centro_x, centro_y = largura * 0.5, altura * 0.16

    meia_l, meia_a = faixa_l / 2, faixa_a / 2
    cantos = []
    for lx, ly in ((-meia_l, -meia_a), (meia_l, -meia_a), (meia_l, meia_a), (-meia_l, meia_a)):
        rx = lx * cos_a - ly * sin_a
        ry = lx * sin_a + ly * cos_a
        cantos.append((centro_x + rx, centro_y + ry))

    draw = ImageDraw.Draw(overlay)
    draw.polygon(cantos, fill=COR_SELO_FUNDO)

    texto_img = Image.new('RGBA', (int(texto_w) + 20, faixa_a), (0, 0, 0, 0))
    draw_texto = ImageDraw.Draw(texto_img)
    draw_texto.text((10, faixa_a * 0.22), texto, font=fonte, fill=(255, 255, 255, 255))
    texto_rotado = texto_img.rotate(angulo_graus, expand=True, resample=Image.BICUBIC)
    pos = (int(centro_x - texto_rotado.width / 2), int(centro_y - texto_rotado.height / 2))
    overlay.alpha_composite(texto_rotado, pos)


def _template_selo_diagonal(overlay, draw, largura, altura, anuncio, chamada):
    """Selo diagonal de "oferta" no canto superior esquerdo (chamada) + faixa
    inferior compacta só com título e preço — comum em anúncios de "promoção"."""
    _selo_diagonal(overlay, chamada, largura, altura)

    margem = int(largura * 0.06)
    largura_util = largura - (2 * margem)
    fonte_titulo = _fonte(largura * 0.05)
    fonte_preco = _fonte(largura * 0.08)

    # o título é a primeira linha da faixa aqui (sem chamada embutida — essa já
    # foi pro selo diagonal), cai na mesma altura do logo — mesma reserva usada
    # na faixa inferior.
    titulo = _titulo_veiculo(anuncio)
    linhas_titulo = _quebrar_linhas(titulo, fonte_titulo, draw, largura_util - int(largura * 0.27))
    espaco_titulo = int(fonte_titulo.size * 1.25)
    espaco_preco = int(fonte_preco.size * 1.35)
    padding = int(largura * 0.05)

    altura_faixa = min(
        padding * 2 + len(linhas_titulo) * espaco_titulo + espaco_preco,
        int(altura * 0.32),
    )
    draw.rectangle([(0, altura - altura_faixa), (largura, altura)], fill=COR_FAIXA)
    _colar_logo(overlay, largura, largura, altura - altura_faixa, altura_faixa)

    y = altura - altura_faixa + padding
    for linha in linhas_titulo:
        _texto_com_contorno(draw, (margem, y), linha, fonte_titulo, COR_TEXTO_PRINCIPAL)
        y += espaco_titulo
    _texto_com_contorno(draw, (margem, y), _formatar_preco(anuncio.preco), fonte_preco, COR_TEXTO_PRECO)


def _template_cartao_central(overlay, draw, largura, altura, anuncio, chamada):
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
    _colar_logo(overlay, largura, margem_lateral + largura_cartao, topo_cartao, altura_pill)

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
    'FAIXA_INFERIOR': _template_faixa_inferior,
    'SELO_DIAGONAL': _template_selo_diagonal,
    'CARTAO_CENTRAL': _template_cartao_central,
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
