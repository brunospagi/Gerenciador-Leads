import requests

BASE_URL = "https://parallelum.com.br/fipe/api/v1/carros"

def get_marcas():
    """Retorna uma lista de todas as marcas de carros."""
    try:
        response = requests.get(f"{BASE_URL}/marcas")
        response.raise_for_status()  # Lança exceção para códigos de erro HTTP
        return response.json()
    except requests.RequestException as e:
        print(f"Erro ao buscar marcas: {e}")
        return None

def get_modelos(marca_id):
    """Retorna os modelos de uma marca específica."""
    try:
        response = requests.get(f"{BASE_URL}/marcas/{marca_id}/modelos")
        response.raise_for_status()
        return response.json().get('modelos', [])
    except requests.RequestException as e:
        print(f"Erro ao buscar modelos para a marca {marca_id}: {e}")
        return None

def get_anos(marca_id, modelo_id):
    """Retorna os anos de um modelo específico."""
    try:
        response = requests.get(f"{BASE_URL}/marcas/{marca_id}/modelos/{modelo_id}/anos")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Erro ao buscar anos para o modelo {modelo_id}: {e}")
        return None

def get_valor_fipe(marca_id, modelo_id, ano_id):
    """Retorna o valor FIPE de um veículo específico."""
    try:
        response = requests.get(f"{BASE_URL}/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_id}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Erro ao buscar valor FIPE: {e}")
        return None