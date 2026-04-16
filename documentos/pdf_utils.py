import base64
import json
import re
import time

from avaliacoes.ai_runtime import get_gemini_runtime


def extract_crlv_data_with_gemini(pdf_file):
    """
    Extrai dados de um PDF CRLV-e usando Gemini multimodal.
    """
    gemini_client, model_name, config_error = get_gemini_runtime()
    if config_error or not gemini_client:
        print(f"Erro: configuração Gemini indisponível. Motivo: {config_error}")
        return None

    try:
        system_instruction = (
            "Você é um assistente de OCR especializado em CRLV-e de veículos brasileiros. "
            "Extraia os campos do PDF e retorne apenas JSON válido com as chaves:\n"
            "- veiculo_renavam\n"
            "- veiculo_placa\n"
            "- veiculo_marca_modelo\n"
            "- veiculo_ano_fab\n"
            "- veiculo_ano_mod\n"
            "- veiculo_cor\n"
            "- outorgante_nome\n"
            "- outorgante_documento\n"
        )

        pdf_file.seek(0)
        pdf_data_base64 = base64.b64encode(pdf_file.read()).decode('utf-8')

        max_attempts = 3
        response = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=[
                        {"text": "Extraia os dados deste documento PDF."},
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": pdf_data_base64,
                            }
                        },
                    ],
                    config={
                        "system_instruction": system_instruction,
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
                print(f"Erro ao processar PDF com Gemini: {e}")
                return None

        if not response:
            return None

        cleaned_json = re.sub(r'```json\s*|\s*```', '', response.text or '', flags=re.DOTALL).strip()
        data = json.loads(cleaned_json)

        if data.get('outorgante_documento'):
            doc_limpo = re.sub(r'\D', '', data['outorgante_documento'])
            data['tipo_documento'] = 'CNPJ' if len(doc_limpo) > 11 else 'CPF'

        return data

    except Exception as e:
        print(f"Erro ao processar PDF com Gemini: {e}")
        return None
