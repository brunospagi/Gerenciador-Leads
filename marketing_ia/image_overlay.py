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
import itertools
import logging
import math
from functools import lru_cache

from django.conf import settings
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

logger = logging.getLogger(__name__)

LOGO_PATH = settings.BASE_DIR / 'static' / 'images' / 'logo-spagi-motors.webp'
_logo_cache = None

FONTS_DIR = settings.BASE_DIR / 'static' / 'fonts'
EMOJI_PNG_DIR = settings.BASE_DIR / 'static' / 'emoji'

# Fontes de verdade (Google Fonts, licença OFL) pra desenhar texto — o
# ImageFont.load_default() do Pillow (fonte "Aileron" embutida) NÃO tem glifos
# de acentuação do português: á, ã, ç, õ etc. saíam como "tofu" (quadradinho
# vazio) em toda imagem gerada. Poppins é a mesma fonte já usada na
# identidade visual do sistema (app_m3.css); as demais são variações de
# estilo oferecidas no editor de layouts.
FONTES = {
    'poppins': FONTS_DIR / 'Poppins-Bold.ttf',
    'poppins_regular': FONTS_DIR / 'Poppins-Regular.ttf',
    'bebas': FONTS_DIR / 'BebasNeue-Regular.ttf',
    'oswald': FONTS_DIR / 'Oswald-Bold.ttf',
    'baloo': FONTS_DIR / 'Baloo2-Bold.ttf',
}
FONTE_PADRAO = 'poppins'
FONTE_EMOJI_PATH = FONTS_DIR / 'NotoEmoji-Regular.ttf'

FONTE_CHOICES = [
    ('poppins', 'Poppins Bold (padrão)'),
    ('poppins_regular', 'Poppins Regular'),
    ('bebas', 'Bebas Neue (impacto/condensada)'),
    ('oswald', 'Oswald (condensada)'),
    ('baloo', 'Baloo 2 (arredondada/divertida)'),
]

# Faixas Unicode que cobrem a esmagadora maioria dos emoji comuns — usado pra
# detectar, dentro de um texto normal (ex: "PROMOÇÃO DE VERÃO 🏖️" digitado no
# "texto fixo" do editor), quais caracteres precisam da fonte de emoji em vez
# da fonte de texto escolhida (Poppins/Bebas/etc não têm glifo de emoji e
# mostravam um "tofu" quebrado no lugar).
FAIXAS_EMOJI = (
    (0x1F300, 0x1FAFF),  # símbolos/pictogramas (a maior faixa, cobre quase tudo)
    (0x2600, 0x27BF),    # símbolos diversos + dingbats (☀️ ✅ etc)
    (0x2B00, 0x2BFF),    # setas/estrelas diversas (⭐ etc)
    (0x1F1E6, 0x1F1FF),  # bandeiras (pares de letra regional)
)
SELETORES_VARIACAO = ('︎', '️')  # dizem "mostra como texto/emoji" — não têm glifo próprio


def _eh_emoji(caractere):
    codepoint = ord(caractere)
    return any(inicio <= codepoint <= fim for inicio, fim in FAIXAS_EMOJI)


def _limpar_selecionadores_variacao(texto):
    """Remove U+FE0E/U+FE0F — são modificadores invisíveis (não têm glifo
    próprio) que vêm colados em alguns emoji (ex: 🏖️, 🏷️); a fonte de emoji
    usada aqui não os trata como zero-width, e sobrava um "tofu" extra do lado
    do emoji ao colar esse tipo de caractere."""
    for seletor in SELETORES_VARIACAO:
        texto = texto.replace(seletor, '')
    return texto

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


@lru_cache(maxsize=256)
def _carregar_fonte_truetype(caminho, tamanho, negrito_se_variavel=True):
    fonte = ImageFont.truetype(str(caminho), tamanho)
    if negrito_se_variavel:
        try:
            fonte.set_variation_by_name('Bold')  # só funciona em fontes variáveis; ignora nas estáticas
        except Exception:
            pass
    return fonte


def _fonte(tamanho, fonte_id=None):
    caminho = FONTES.get(fonte_id, FONTES[FONTE_PADRAO])
    return _carregar_fonte_truetype(caminho, max(int(tamanho), 10))


def _arquivo_png_emoji(emoji_texto):
    """Nome do PNG colorido do Twemoji (codepoints em hex, sem seletor de
    variação, separados por hífen) pro emoji informado, se tivermos ele
    bundlado em static/emoji/. Emoji fora desse conjunto caem no fallback de
    fonte vetorial (_desenhar_texto_misto/_desenhar_elemento_emoji) — assim
    QUALQUER emoji colado funciona, só que sem cor quando não bundlado."""
    codepoints = '-'.join(format(ord(c), 'x') for c in emoji_texto if ord(c) != 0xFE0F)
    if not codepoints:
        return None
    caminho = EMOJI_PNG_DIR / f'{codepoints}.png'
    return caminho if caminho.exists() else None


@lru_cache(maxsize=128)
def _carregar_emoji_png_original(caminho):
    return Image.open(caminho).convert('RGBA')


def _carregar_emoji_png(caminho, tamanho):
    original = _carregar_emoji_png_original(caminho)
    return original.resize((max(int(tamanho), 1), max(int(tamanho), 1)), Image.LANCZOS)


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
    partes = [(anuncio.marca or '').upper(), (anuncio.modelo or '').upper()]
    motorizacao = getattr(anuncio, 'motorizacao', None)
    if motorizacao:
        partes.append(motorizacao.upper())
    if anuncio.ano:
        partes.append(str(anuncio.ano))
    return ' '.join(p for p in partes if p).strip()


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


def _desenhar_texto_misto(overlay, draw, posicao, texto, fonte_texto, tamanho_fonte, cor_texto):
    """Desenha uma linha alternando entre a fonte de texto escolhida e emoji
    conforme o caractere — permite colar emoji no meio de texto normal (ex:
    "PROMOÇÃO DE VERÃO 🏖️" no campo de texto fixo do editor) sem virar um
    retângulo vazio, já que Poppins/Bebas/Oswald/Baloo não têm glifo de
    emoji. Cada emoji tenta primeiro o PNG colorido do Twemoji (bundlado em
    static/emoji/); se não tiver esse emoji específico bundlado, cai pro
    contorno vetorial da fonte NotoEmoji — assim QUALQUER emoji colado
    funciona, não só os que estão no teclado do editor."""
    x, y = posicao
    fonte_emoji = None
    for eh_emoji, grupo in itertools.groupby(texto, key=_eh_emoji):
        trecho = ''.join(grupo)
        if not eh_emoji:
            _texto_com_contorno(draw, (x, y), trecho, fonte_texto, cor_texto)
            x += draw.textlength(trecho, font=fonte_texto)
            continue
        for caractere in trecho:
            caminho_png = _arquivo_png_emoji(caractere)
            if caminho_png:
                emoji_img = _carregar_emoji_png(caminho_png, tamanho_fonte)
                overlay.alpha_composite(emoji_img, (int(x), int(y)))
                x += tamanho_fonte
            else:
                if fonte_emoji is None:
                    fonte_emoji = _carregar_fonte_truetype(FONTE_EMOJI_PATH, tamanho_fonte, negrito_se_variavel=False)
                draw.text((x, y), caractere, font=fonte_emoji, fill=cor_texto)
                x += draw.textlength(caractere, font=fonte_emoji)


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

# Aproximação dos 3 templates fixos em formato de camadas (usado pelo editor
# drag-and-drop como ponto de partida ao "clonar" um template existente pra
# customizar). O selo diagonal do SELO_DIAGONAL não tem equivalente livre — vira
# uma pill reta no topo, como a chamada do CARTAO_CENTRAL.
ELEMENTOS_BASE = {
    'FAIXA_INFERIOR': [
        {'tipo': 'forma', 'x': 0, 'y': 0.68, 'largura': 1, 'altura': 0.32,
         'cor_fundo': '#0f172a', 'opacidade': 0.92, 'arredondado': 0},
        {'tipo': 'texto', 'campo': 'chamada', 'x': 0.06, 'y': 0.715, 'largura': 0.65,
         'tamanho_fonte': 0.055, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.80, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.88, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#4ade80', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.705, 'altura': 0.07},
    ],
    'SELO_DIAGONAL': [
        {'tipo': 'forma', 'x': 0, 'y': 0.76, 'largura': 1, 'altura': 0.24,
         'cor_fundo': '#0f172a', 'opacidade': 0.92, 'arredondado': 0},
        {'tipo': 'forma', 'x': 0.06, 'y': 0.04, 'largura': 0.55, 'altura': 0.06,
         'cor_fundo': '#c52b30', 'opacidade': 1, 'arredondado': 0.03},
        {'tipo': 'texto', 'campo': 'chamada', 'x': 0.08, 'y': 0.052, 'largura': 0.5,
         'tamanho_fonte': 0.04, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.80, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#4ade80', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.785, 'altura': 0.06},
    ],
    'CARTAO_CENTRAL': [
        {'tipo': 'forma', 'x': 0.06, 'y': 0.58, 'largura': 0.88, 'altura': 0.37,
         'cor_fundo': '#0f172a', 'opacidade': 0.92, 'arredondado': 0.04},
        {'tipo': 'forma', 'x': 0.11, 'y': 0.615, 'largura': 0.4, 'altura': 0.06,
         'cor_fundo': '#c52b30', 'opacidade': 1, 'arredondado': 0.03},
        {'tipo': 'texto', 'campo': 'chamada', 'x': 0.13, 'y': 0.628, 'largura': 0.35,
         'tamanho_fonte': 0.04, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.11, 'y': 0.71, 'largura': 0.78,
         'tamanho_fonte': 0.05, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.11, 'y': 0.82, 'largura': 0.78,
         'tamanho_fonte': 0.07, 'cor_texto': '#4ade80', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.78, 'y': 0.60, 'altura': 0.05},
    ],
}

# Pontos de partida temáticos pra datas comemorativas — mesma ideia do
# ELEMENTOS_BASE (clonar e ajustar), só que com cores/fontes/emoji do tema em
# vez de replicar um template neutro. Aparecem como opção extra em "Criar a
# partir de um template pronto" na listagem de layouts.
ELEMENTOS_DATAS_COMEMORATIVAS = {
    'NATAL': [
        {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
         'cor_fundo': '#165b33', 'opacidade': 0.93, 'arredondado': 0},
        {'tipo': 'emoji', 'emoji': '🎄', 'x': 0.04, 'y': 0.03, 'altura': 0.12},
        {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'FELIZ NATAL', 'x': 0.06, 'y': 0.725, 'largura': 0.7,
         'tamanho_fonte': 0.06, 'cor_texto': '#f8b229', 'fonte': 'bebas', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.81, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#f8b229', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.71, 'altura': 0.06},
    ],
    'ANO_NOVO': [
        {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
         'cor_fundo': '#0b0b0f', 'opacidade': 0.93, 'arredondado': 0},
        {'tipo': 'emoji', 'emoji': '🎉', 'x': 0.04, 'y': 0.03, 'altura': 0.12},
        {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'ANO NOVO, CARRO NOVO', 'x': 0.06, 'y': 0.725, 'largura': 0.85,
         'tamanho_fonte': 0.05, 'cor_texto': '#d4af37', 'fonte': 'oswald', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.81, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#d4af37', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.71, 'altura': 0.06},
    ],
    'BLACK_FRIDAY': [
        {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
         'cor_fundo': '#000000', 'opacidade': 0.94, 'arredondado': 0},
        {'tipo': 'emoji', 'emoji': '🔥', 'x': 0.04, 'y': 0.03, 'altura': 0.12},
        {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'BLACK FRIDAY', 'x': 0.06, 'y': 0.72, 'largura': 0.85,
         'tamanho_fonte': 0.065, 'cor_texto': '#ffcc00', 'fonte': 'bebas', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.81, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#ffcc00', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.71, 'altura': 0.06},
    ],
    'DIA_DAS_MAES': [
        {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
         'cor_fundo': '#7a3b69', 'opacidade': 0.9, 'arredondado': 0},
        {'tipo': 'emoji', 'emoji': '💐', 'x': 0.04, 'y': 0.03, 'altura': 0.12},
        {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'DIA DAS MÃES', 'x': 0.06, 'y': 0.725, 'largura': 0.7,
         'tamanho_fonte': 0.06, 'cor_texto': '#ffd6ec', 'fonte': 'baloo', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.81, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#4ade80', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.71, 'altura': 0.06},
    ],
    'DIA_DOS_PAIS': [
        {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
         'cor_fundo': '#0b3d66', 'opacidade': 0.92, 'arredondado': 0},
        {'tipo': 'emoji', 'emoji': '🎁', 'x': 0.04, 'y': 0.03, 'altura': 0.12},
        {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'DIA DOS PAIS', 'x': 0.06, 'y': 0.725, 'largura': 0.7,
         'tamanho_fonte': 0.06, 'cor_texto': '#7ec8ff', 'fonte': 'oswald', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.81, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#4ade80', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.71, 'altura': 0.06},
    ],
    'CARNAVAL': [
        {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
         'cor_fundo': '#6a1b9a', 'opacidade': 0.9, 'arredondado': 0},
        {'tipo': 'emoji', 'emoji': '🎭', 'x': 0.04, 'y': 0.03, 'altura': 0.12},
        {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'FOLIA NO CARNAVAL', 'x': 0.06, 'y': 0.72, 'largura': 0.85,
         'tamanho_fonte': 0.05, 'cor_texto': '#ffd600', 'fonte': 'baloo', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.81, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#ffd600', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.71, 'altura': 0.06},
    ],
    'PASCOA': [
        {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
         'cor_fundo': '#7a4a1e', 'opacidade': 0.9, 'arredondado': 0},
        {'tipo': 'emoji', 'emoji': '🐰', 'x': 0.04, 'y': 0.03, 'altura': 0.12},
        {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'FELIZ PÁSCOA', 'x': 0.06, 'y': 0.725, 'largura': 0.7,
         'tamanho_fonte': 0.06, 'cor_texto': '#ffe0b2', 'fonte': 'baloo', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.81, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#4ade80', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.71, 'altura': 0.06},
    ],
    'DIA_DOS_NAMORADOS': [
        {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
         'cor_fundo': '#8e0038', 'opacidade': 0.9, 'arredondado': 0},
        {'tipo': 'emoji', 'emoji': '❤️', 'x': 0.04, 'y': 0.03, 'altura': 0.12},
        {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'DIA DOS NAMORADOS', 'x': 0.06, 'y': 0.725, 'largura': 0.85,
         'tamanho_fonte': 0.05, 'cor_texto': '#ff8fab', 'fonte': 'baloo', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.81, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#ff8fab', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.71, 'altura': 0.06},
    ],
    'FESTA_JUNINA': [
        {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
         'cor_fundo': '#5a3921', 'opacidade': 0.92, 'arredondado': 0},
        {'tipo': 'emoji', 'emoji': '🎆', 'x': 0.04, 'y': 0.03, 'altura': 0.12},
        {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'ARRAIÁ DE OFERTAS', 'x': 0.06, 'y': 0.72, 'largura': 0.85,
         'tamanho_fonte': 0.05, 'cor_texto': '#ff6f00', 'fonte': 'bebas', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.81, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#ff6f00', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.71, 'altura': 0.06},
    ],
    'DIA_DAS_CRIANCAS': [
        {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
         'cor_fundo': '#0277bd', 'opacidade': 0.9, 'arredondado': 0},
        {'tipo': 'emoji', 'emoji': '🎈', 'x': 0.04, 'y': 0.03, 'altura': 0.12},
        {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'DIA DAS CRIANÇAS', 'x': 0.06, 'y': 0.725, 'largura': 0.85,
         'tamanho_fonte': 0.05, 'cor_texto': '#ffeb3b', 'fonte': 'baloo', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.81, 'largura': 0.88,
         'tamanho_fonte': 0.045, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda', 'maiusculas': True},
        {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.89, 'largura': 0.88,
         'tamanho_fonte': 0.07, 'cor_texto': '#ffeb3b', 'alinhamento': 'esquerda', 'maiusculas': False},
        {'tipo': 'logo', 'x': 0.80, 'y': 0.71, 'altura': 0.06},
    ],
}

DATA_COMEMORATIVA_CHOICES = [
    ('NATAL', 'Natal'),
    ('ANO_NOVO', 'Ano Novo'),
    ('BLACK_FRIDAY', 'Black Friday'),
    ('DIA_DAS_MAES', 'Dia das Mães'),
    ('DIA_DOS_PAIS', 'Dia dos Pais'),
    ('CARNAVAL', 'Carnaval'),
    ('PASCOA', 'Páscoa'),
    ('DIA_DOS_NAMORADOS', 'Dia dos Namorados'),
    ('FESTA_JUNINA', 'Festa Junina'),
    ('DIA_DAS_CRIANCAS', 'Dia das Crianças'),
]


def _cor_de_hex(hex_cor, opacidade=1.0):
    """Converte '#rrggbb' (formato do <input type=color>) pra tupla RGBA
    0-255, aplicando a opacidade (0-1) no canal alfa."""
    hex_cor = (hex_cor or '').lstrip('#')
    if len(hex_cor) != 6:
        hex_cor = '0f172a'
    r, g, b = (int(hex_cor[i:i + 2], 16) for i in (0, 2, 4))
    alfa = max(0, min(255, int(float(opacidade if opacidade is not None else 1.0) * 255)))
    return (r, g, b, alfa)


def _texto_do_elemento(elemento, anuncio, chamada):
    campo = elemento.get('campo', 'fixo')
    if campo == 'chamada':
        texto = chamada or ''
    elif campo == 'titulo':
        texto = _titulo_veiculo(anuncio)
    elif campo == 'preco':
        texto = _formatar_preco(anuncio.preco)
    elif campo == 'opcionais':
        # só os primeiros itens, pra não virar uma parede de texto na imagem.
        opcionais = getattr(anuncio, 'opcionais', None) or []
        texto = ', '.join(opcionais[:4])
    elif campo == 'veiculo_completo':
        # texto vazio quando a flag não está marcada — o elemento simplesmente
        # não aparece na imagem (mesmo comportamento de qualquer texto vazio).
        texto = 'Veículo Completo' if getattr(anuncio, 'veiculo_completo', False) else ''
    else:
        texto = elemento.get('texto_fixo') or ''
    if elemento.get('maiusculas', True):
        texto = texto.upper()
    return _limpar_selecionadores_variacao(texto)


def _desenhar_elemento_forma(draw, elemento, largura, altura):
    x = int(float(elemento.get('x', 0)) * largura)
    y = int(float(elemento.get('y', 0)) * altura)
    w = max(int(float(elemento.get('largura', 0.2)) * largura), 1)
    h = max(int(float(elemento.get('altura', 0.1)) * altura), 1)
    cor = _cor_de_hex(elemento.get('cor_fundo'), elemento.get('opacidade', 0.9))
    formato = elemento.get('formato', 'retangulo')
    if formato == 'circulo':
        draw.ellipse([(x, y), (x + w, y + h)], fill=cor)
        return
    raio = float(elemento.get('arredondado') or 0)
    if raio > 0:
        draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=int(raio * largura), fill=cor)
    else:
        draw.rectangle([(x, y), (x + w, y + h)], fill=cor)


def _desenhar_elemento_texto(overlay, draw, elemento, anuncio, chamada, largura, altura):
    texto = _texto_do_elemento(elemento, anuncio, chamada)
    if not texto:
        return
    x = int(float(elemento.get('x', 0)) * largura)
    y = int(float(elemento.get('y', 0)) * altura)
    w = max(int(float(elemento.get('largura', 0.8)) * largura), 10)
    tamanho_fonte = max(int(float(elemento.get('tamanho_fonte', 0.05)) * largura), 10)
    fonte = _fonte(tamanho_fonte, elemento.get('fonte'))
    cor_texto = _cor_de_hex(elemento.get('cor_texto'), 1.0) if elemento.get('cor_texto') else COR_TEXTO_PRINCIPAL
    alinhamento = elemento.get('alinhamento', 'esquerda')

    linhas = _quebrar_linhas(texto, fonte, draw, w) or [texto]
    espaco_linha = int(tamanho_fonte * 1.25)
    linha_y = y
    for linha in linhas:
        linha_x = x
        if alinhamento == 'centro':
            linha_largura = draw.textlength(linha, font=fonte)
            linha_x = x + max(int((w - linha_largura) / 2), 0)
        _desenhar_texto_misto(overlay, draw, (linha_x, linha_y), linha, fonte, tamanho_fonte, cor_texto)
        linha_y += espaco_linha


def _desenhar_elemento_logo(overlay, elemento, largura, altura):
    logo = _carregar_logo()
    if logo is None:
        return
    x = int(float(elemento.get('x', 0)) * largura)
    y = int(float(elemento.get('y', 0)) * altura)
    altura_logo = max(int(float(elemento.get('altura', 0.06)) * altura), 1)
    largura_logo = max(int(logo.width * (altura_logo / logo.height)), 1)
    logo_redimensionado = logo.resize((largura_logo, altura_logo), Image.LANCZOS)
    overlay.alpha_composite(logo_redimensionado, (x, y))


def _desenhar_elemento_emoji(overlay, elemento, largura, altura):
    """Emoji como um 'adesivo' separado. Tenta primeiro o PNG colorido do
    Twemoji (bundlado em static/emoji/ — visual "de verdade", não só um
    contorno); se esse emoji específico não estiver bundlado, cai pro
    contorno vetorial da fonte NotoEmoji, que cobre praticamente qualquer
    emoji Unicode (sem cor, mas sem virar "tofu" também)."""
    emoji = _limpar_selecionadores_variacao((elemento.get('emoji') or '').strip())
    if not emoji:
        return
    tamanho = max(int(float(elemento.get('altura', 0.08)) * altura), 10)
    x = int(float(elemento.get('x', 0)) * largura)
    y = int(float(elemento.get('y', 0)) * altura)

    caminho_png = _arquivo_png_emoji(emoji)
    if caminho_png:
        emoji_img = _carregar_emoji_png(caminho_png, tamanho)
        overlay.alpha_composite(emoji_img, (x, y))
        return

    fonte = _carregar_fonte_truetype(FONTE_EMOJI_PATH, tamanho, negrito_se_variavel=False)
    cor = _cor_de_hex(elemento.get('cor'), 1.0) if elemento.get('cor') else COR_TEXTO_PRINCIPAL
    draw = ImageDraw.Draw(overlay)
    draw.text((x, y), emoji, font=fonte, fill=cor)


def montar_imagem_layout(foto_bytes, anuncio, chamada, elementos, resolucao=None):
    """
    Renderiza a partir de uma lista de elementos livremente posicionados (o
    editor drag-and-drop de LayoutOverlay), em vez de um dos 3 templates fixos.
    Cada elemento é uma camada (desenhada na ordem da lista — os de baixo
    ficam por cima) com posição/tamanho em frações 0-1 do canvas. Um elemento
    com dado inválido é pulado (loga e segue pros próximos) em vez de derrubar
    a imagem inteira. Retorna (bytes, mime_type) ou levanta ImageOverlayError.
    """
    tamanho_saida = RESOLUCOES.get(resolucao, RESOLUCOES[RESOLUCAO_PADRAO])
    base = _preparar_foto(foto_bytes, tamanho_saida).convert('RGBA')
    largura, altura = base.size

    overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for elemento in (elementos or []):
        tipo = elemento.get('tipo') if isinstance(elemento, dict) else None
        try:
            if tipo == 'forma':
                _desenhar_elemento_forma(draw, elemento, largura, altura)
            elif tipo == 'texto':
                _desenhar_elemento_texto(overlay, draw, elemento, anuncio, chamada, largura, altura)
            elif tipo == 'logo':
                _desenhar_elemento_logo(overlay, elemento, largura, altura)
            elif tipo == 'emoji':
                _desenhar_elemento_emoji(overlay, elemento, largura, altura)
        except Exception as exc:
            logger.warning('Erro ao desenhar elemento "%s" do layout customizado: %s', tipo, exc)
            continue

    final = Image.alpha_composite(base, overlay).convert('RGB')
    saida = io.BytesIO()
    final.save(saida, format='JPEG', quality=90)
    return saida.getvalue(), 'image/jpeg'


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
