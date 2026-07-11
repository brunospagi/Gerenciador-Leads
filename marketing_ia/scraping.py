import logging
import os
import re
import time
from decimal import Decimal, InvalidOperation

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

BASE_URL = 'https://www.spagimotors.com.br'
SEARCH_URL = f'{BASE_URL}/search'

ID_RE = re.compile(r'id-(\d+)/?$')
PRECO_RE = re.compile(r'[^\d,]')


def build_driver(headless=True):
    """
    Monta o Chrome do Selenium. Em produção (Docker) usa os binários apontados
    por CHROME_BIN/CHROMEDRIVER_BIN (instalados via apt no Dockerfile). Em
    desenvolvimento local, deixa o Selenium Manager descobrir o Chrome instalado.
    """
    options = Options()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1366,900')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')

    chrome_bin = os.getenv('CHROME_BIN')
    if chrome_bin:
        options.binary_location = chrome_bin

    chromedriver_bin = os.getenv('CHROMEDRIVER_BIN')
    service = Service(executable_path=chromedriver_bin) if chromedriver_bin else Service()

    return webdriver.Chrome(service=service, options=options)


def _texto(el):
    return (el.text or '').strip()


def _extrair_id_externo(url):
    m = ID_RE.search(url or '')
    return m.group(1) if m else None


def _parse_preco(texto):
    if not texto:
        return None
    limpo = PRECO_RE.sub('', texto).replace(',', '.')
    try:
        return Decimal(limpo)
    except (InvalidOperation, ValueError):
        return None


def _classificar_tipo(features_texto):
    features_texto = (features_texto or '').upper()
    motos = ('MOTO', 'TRICICLO', 'QUADRICICLO')
    if any(p in features_texto for p in motos):
        return 'MOTO'
    return 'CARRO'


def _extrair_cards_da_pagina_atual(driver):
    itens = []
    for card in driver.find_elements(By.CSS_SELECTOR, '.card__wrapper .card'):
        try:
            link_el = card.find_element(By.CSS_SELECTOR, 'a.card__content, a.card__figure')
            url = link_el.get_attribute('href')
            if not url or not _extrair_id_externo(url):
                continue

            titulo = _texto(card.find_element(By.CSS_SELECTOR, '.card__title'))
            try:
                preco_texto = _texto(card.find_element(By.CSS_SELECTOR, '.card__sell__value'))
            except NoSuchElementException:
                preco_texto = None
            try:
                features_texto = _texto(card.find_element(By.CSS_SELECTOR, '.card__features'))
            except NoSuchElementException:
                features_texto = ''
            try:
                img_el = card.find_element(By.CSS_SELECTOR, '.card__image')
                # O site usa lazy-load: só os cards já visíveis na tela no momento
                # do carregamento têm o atributo `src` preenchido — os demais só
                # têm a URL real em `data-src`, até o usuário rolar a página.
                foto_url = img_el.get_attribute('src') or img_el.get_attribute('data-src')
            except NoSuchElementException:
                foto_url = None

            itens.append({
                'url': url,
                'titulo': titulo,
                'preco': _parse_preco(preco_texto),
                'tipo': _classificar_tipo(features_texto),
                'foto_url': foto_url,
            })
        except NoSuchElementException:
            continue
    return itens


def coletar_links_estoque(driver, max_paginas=None, espera=8):
    """
    Percorre as páginas de /search e retorna uma lista de dicts básicos
    (url, titulo, preco, tipo) — um por card de veículo encontrado.

    A quantidade de páginas é descoberta a partir do contador nativo do site
    ("Exibindo 1 - 20 de N"), que sempre lista 20 itens por página.
    """
    wait = WebDriverWait(driver, espera)
    driver.get(SEARCH_URL)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.card__wrapper .card')))
    except TimeoutException:
        logger.info('Nenhum card encontrado em %s.', SEARCH_URL)
        return []

    resultados = _extrair_cards_da_pagina_atual(driver)

    total_itens = None
    try:
        texto_contador = _texto(driver.find_element(By.CSS_SELECTOR, '.pagination__quantity'))
        m = re.search(r'de\s+(\d+)', texto_contador)
        if m:
            total_itens = int(m.group(1))
    except NoSuchElementException:
        pass

    itens_por_pagina = len(resultados) or 20
    total_paginas = 1
    if total_itens:
        total_paginas = max(1, -(-total_itens // itens_por_pagina))  # ceil
    if max_paginas:
        total_paginas = min(total_paginas, max_paginas)

    for pagina in range(2, total_paginas + 1):
        driver.get(f'{SEARCH_URL}/pagina.{pagina}')
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.card__wrapper .card')))
        except TimeoutException:
            break
        resultados.extend(_extrair_cards_da_pagina_atual(driver))

    # Dedup por URL, preservando ordem.
    vistos = set()
    unicos = []
    for item in resultados:
        if item['url'] in vistos:
            continue
        vistos.add(item['url'])
        unicos.append(item)
    return unicos


def _campo_tecnico(driver, rotulo):
    """Lê um par rótulo/valor dentro de .vehicle__technical__information."""
    try:
        blocos = driver.find_elements(By.CSS_SELECTOR, '.vehicle__technical__information')
    except NoSuchElementException:
        return None
    rotulo_upper = rotulo.upper()
    for bloco in blocos:
        try:
            tipo = _texto(bloco.find_element(By.CSS_SELECTOR, '.vehicle__technical__information__type'))
            if tipo.upper() == rotulo_upper:
                return _texto(bloco.find_element(By.CSS_SELECTOR, '.vehicle__technical__information__value'))
        except NoSuchElementException:
            continue
    return None


def extrair_detalhes_anuncio(driver, url, foto_url=None, espera=8):
    """
    Abre a página de detalhe de um anúncio e extrai os campos relevantes
    (specs, opcionais, descrição). A foto NÃO é lida do carrossel desta
    página: o carrossel usa Glide.js e reaproveitamos a mesma sessão do
    Selenium entre veículos, então o `data-src-hd` às vezes ainda reflete o
    slide do veículo anterior quando lemos logo após o `driver.get()`,
    resultando em foto trocada. A miniatura já coletada na listagem
    (`foto_url`, vindo de `.card__image` em /search) é confiável e usada
    como foto principal.
    """
    wait = WebDriverWait(driver, espera)
    driver.get(url)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.vehicle__title')))

    external_id = _extrair_id_externo(url)
    titulo = _texto(driver.find_element(By.CSS_SELECTOR, '.vehicle__title'))

    try:
        marca_modelo = _texto(driver.find_element(By.CSS_SELECTOR, '.vehicle__model'))
    except NoSuchElementException:
        marca_modelo = ''
    partes_marca_modelo = marca_modelo.split(maxsplit=1)
    marca = partes_marca_modelo[0].title() if partes_marca_modelo else None
    modelo = partes_marca_modelo[1].title() if len(partes_marca_modelo) > 1 else None

    try:
        preco = _parse_preco(_texto(driver.find_element(By.CSS_SELECTOR, '.vehicle__sell__value')))
    except NoSuchElementException:
        preco = None

    try:
        condicoes = [
            _texto(el) for el in driver.find_elements(By.CSS_SELECTOR, '.vehicle__condition__text')
        ]
    except NoSuchElementException:
        condicoes = []

    try:
        opcionais = [
            _texto(el) for el in driver.find_elements(By.CSS_SELECTOR, '.vehicle__optionals__optional')
        ]
    except NoSuchElementException:
        opcionais = []

    try:
        descricao = _texto(driver.find_element(By.CSS_SELECTOR, '.vehicle__details__content'))
    except NoSuchElementException:
        descricao = ''

    fotos_urls = [foto_url] if foto_url else []

    features_texto = f"{marca_modelo} {titulo}"

    return {
        'external_id': external_id,
        'url': url,
        'tipo': _classificar_tipo(features_texto),
        'marca': marca,
        'modelo': modelo,
        'titulo': titulo,
        'preco': preco,
        'ano': _campo_tecnico(driver, 'Ano'),
        'km': _campo_tecnico(driver, 'KM'),
        'cor': _campo_tecnico(driver, 'Cor'),
        'cambio': _campo_tecnico(driver, 'Câmbio'),
        'combustivel': _campo_tecnico(driver, 'Combustível'),
        'carroceria': _campo_tecnico(driver, 'Carroceria'),
        'portas': _campo_tecnico(driver, 'Portas'),
        'condicoes': condicoes,
        'opcionais': opcionais,
        'descricao': descricao,
        'foto_principal_url': fotos_urls[0] if fotos_urls else None,
        'fotos_urls': fotos_urls,
    }


def scrape_estoque(max_paginas=None, tipo=None, limit=None, incluir_detalhes=True, progress_cb=None):
    """
    Orquestra o scraping completo: lista os cards do /search e, opcionalmente,
    visita cada anúncio para extrair os detalhes completos.

    `progress_cb`, se informado, é chamado como progress_cb(indice, total, titulo)
    a cada anúncio processado — útil para logar progresso no management command.
    """
    driver = build_driver()
    try:
        links = coletar_links_estoque(driver, max_paginas=max_paginas)
        if tipo:
            links = [item for item in links if item['tipo'] == tipo]
        if limit:
            links = links[:limit]

        if not incluir_detalhes:
            return links

        detalhados = []
        total = len(links)
        for indice, item in enumerate(links, start=1):
            try:
                detalhes = extrair_detalhes_anuncio(driver, item['url'], foto_url=item.get('foto_url'))
                detalhados.append(detalhes)
            except (TimeoutException, NoSuchElementException, WebDriverException) as exc:
                logger.warning('Falha ao extrair detalhes de %s: %s', item['url'], exc)
                continue
            finally:
                if progress_cb:
                    progress_cb(indice, total, item.get('titulo'))
                time.sleep(0.5)
        return detalhados
    finally:
        driver.quit()
