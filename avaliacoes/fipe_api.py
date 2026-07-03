import logging

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://parallelum.com.br/fipe/api/v1/carros"
TIMEOUT_SECONDS = 5

def get_marcas():
    """Retorna uma lista de todas as marcas de carros."""
    try:
        response = requests.get(f"{BASE_URL}/marcas", timeout=TIMEOUT_SECONDS)
        response.raise_for_status()  # Lança exceção para códigos de erro HTTP
        return response.json()
    except requests.RequestException as e:
        logger.warning("Erro ao buscar marcas FIPE: %s", e)
        return None

def get_modelos(marca_id):
    """Retorna os modelos de uma marca específica."""
    try:
        response = requests.get(f"{BASE_URL}/marcas/{marca_id}/modelos", timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json().get('modelos', [])
    except requests.RequestException as e:
        logger.warning("Erro ao buscar modelos FIPE para a marca %s: %s", marca_id, e)
        return None

def get_anos(marca_id, modelo_id):
    """Retorna os anos de um modelo específico."""
    try:
        response = requests.get(f"{BASE_URL}/marcas/{marca_id}/modelos/{modelo_id}/anos", timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.warning("Erro ao buscar anos FIPE para o modelo %s: %s", modelo_id, e)
        return None

def get_valor_fipe(marca_id, modelo_id, ano_id):
    """Retorna o valor FIPE de um veículo específico."""
    try:
        response = requests.get(f"{BASE_URL}/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_id}", timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.warning("Erro ao buscar valor FIPE: %s", e)
        return None
