import base64
import json
import logging
import mimetypes
import re
import time

from avaliacoes.ai_runtime import get_gemini_runtime

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "Você é um assistente que valida comprovantes de pagamento brasileiros (Pix, TED, DOC, "
    "transferência bancária, recibo de cartão). Analise o arquivo enviado e diga se ele é um "
    "comprovante de pagamento legítimo e legível, com informações como valor, data e "
    "origem/destino visíveis. Considere inválido se o arquivo estiver ilegível, cortado, "
    "não for um comprovante de pagamento, ou não tiver dados mínimos de uma transação.\n"
    "Retorne apenas JSON válido com as chaves:\n"
    "- valido (true/false)\n"
    "- motivo (string curta em português explicando o motivo da decisão)\n"
)


def validar_comprovante_com_gemini(comprovante_field):
    """
    Recebe o FieldFile do comprovante e retorna {'valido': bool, 'motivo': str}.
    Retorna None se a IA estiver indisponível ou ocorrer qualquer erro — o chamador
    deve manter o status como não verificado nesse caso, sem travar o fluxo de venda.
    """
    gemini_client, model_name, config_error = get_gemini_runtime()
    if config_error or not gemini_client:
        logger.warning("Gemini indisponível para validar comprovante: %s", config_error)
        return None

    try:
        comprovante_field.open('rb')
        try:
            file_bytes = comprovante_field.read()
        finally:
            comprovante_field.close()

        mime_type = mimetypes.guess_type(comprovante_field.name)[0] or 'image/jpeg'
        data_base64 = base64.b64encode(file_bytes).decode('utf-8')

        max_attempts = 3
        response = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=[
                        {"text": "Valide se este arquivo é um comprovante de pagamento legítimo e legível."},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": data_base64,
                            }
                        },
                    ],
                    config={
                        "system_instruction": SYSTEM_INSTRUCTION,
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
                logger.warning("Erro ao validar comprovante com Gemini: %s", e)
                return None

        if not response:
            return None

        cleaned_json = re.sub(r'```json\s*|\s*```', '', response.text or '', flags=re.DOTALL).strip()
        data = json.loads(cleaned_json)
        return {
            'valido': bool(data.get('valido')),
            'motivo': (data.get('motivo') or '').strip(),
        }

    except Exception as e:
        logger.warning("Erro ao validar comprovante com Gemini: %s", e)
        return None
