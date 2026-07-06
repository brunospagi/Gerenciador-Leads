import base64
import json
import logging
import mimetypes
import re
import time

from avaliacoes.ai_runtime import get_gemini_runtime

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION_CLIENTE = (
    "Você é um assistente de OCR especializado em documentos de identificação "
    "brasileiros (RG ou CNH). Extraia os dados visíveis do documento enviado.\n"
    "Retorne apenas JSON válido com as chaves:\n"
    "- nome (nome completo, ou null se não encontrar)\n"
    "- cpf (apenas se estiver visível no documento, ou null)\n"
    "- rg (número do RG/registro, ou null)\n"
    "- data_nascimento (formato AAAA-MM-DD, ou null se não encontrar)\n"
)


def extrair_dados_cliente_com_gemini(arquivo):
    """
    Recebe um arquivo de RG/CNH (imagem ou PDF) e retorna um dict com
    {'nome', 'cpf', 'rg', 'data_nascimento'}. Retorna None se a IA estiver
    indisponível ou ocorrer qualquer erro — o chamador deve seguir o fluxo
    normalmente nesse caso, sem bloquear a criação da venda.
    """
    gemini_client, model_name, config_error = get_gemini_runtime()
    if config_error or not gemini_client:
        logger.warning("Gemini indisponível para extrair documento do cliente: %s", config_error)
        return None

    try:
        arquivo.open('rb')
        try:
            file_bytes = arquivo.read()
        finally:
            arquivo.close()

        mime_type = mimetypes.guess_type(arquivo.name)[0] or 'image/jpeg'
        data_base64 = base64.b64encode(file_bytes).decode('utf-8')

        max_attempts = 3
        response = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=[
                        {"text": "Extraia os dados deste documento de identificação."},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": data_base64,
                            }
                        },
                    ],
                    config={
                        "system_instruction": SYSTEM_INSTRUCTION_CLIENTE,
                        "response_mime_type": "application/json",
                    },
                )
                break
            except Exception as e:
                error_upper = str(e).upper()
                is_transient = (
                    '503' in error_upper
                    or 'UNAVAILABLE' in error_upper
                    or 'HIGH DEMAND' in error_upper
                )
                if is_transient and attempt < max_attempts:
                    time.sleep(attempt)
                    continue
                logger.warning("Erro ao extrair documento do cliente com Gemini: %s", e)
                return None

        if not response:
            return None

        cleaned_json = re.sub(r'```json\s*|\s*```', '', response.text or '', flags=re.DOTALL).strip()
        data = json.loads(cleaned_json)
        return {
            'nome': data.get('nome') or None,
            'cpf': data.get('cpf') or None,
            'rg': data.get('rg') or None,
            'data_nascimento': data.get('data_nascimento') or None,
        }

    except Exception as e:
        logger.warning("Erro ao extrair documento do cliente com Gemini: %s", e)
        return None
