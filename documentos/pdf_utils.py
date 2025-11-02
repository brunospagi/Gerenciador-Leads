import google.genai as genai
import google.generativeai.types as genai_types # <-- IMPORT NECESSÁRIO
from django.conf import settings
import json
import re
from io import BytesIO

# 1. Inicializa o cliente
try:
    GEMINI_CLIENT = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
except ImportError:
    GEMINI_CLIENT = None
except ValueError:
    GEMINI_CLIENT = None

def extract_crlv_data_with_gemini(pdf_file):
    """
    Extrai dados de um arquivo PDF CRLV-e usando a API Gemini (multimodal).
    Isso funciona para PDFs baseados em texto e PDFs baseados em imagem (scans).
    """
    if not GEMINI_CLIENT:
        print("Erro: API Key do Gemini não configurada.")
        return None

    try:
        # 2. Prepara o prompt (System Instruction)
        system_instruction = (
            "Você é um assistente de OCR (Reconhecimento Óptico de Caracteres) "
            "especializado em ler documentos de veículos brasileiros (CRLV-e)."
            "Sua tarefa é extrair os campos-chave do documento PDF fornecido e "
            "retornar *apenas* um objeto JSON válido. "
            "Mapeie os campos do PDF para as seguintes chaves JSON:\n"
            "- Código RENAVAM -> 'veiculo_renavam'\n"
            "- Placa -> 'veiculo_placa'\n"
            "- Marca/Modelo/Versão -> 'veiculo_marca_modelo'\n"
            "- Ano Fabricação -> 'veiculo_ano_fab'\n"
            "- Ano Modelo -> 'veiculo_ano_mod'\n"
            "- Cor Predominante -> 'veiculo_cor'\n"
            "- Nome (do proprietário) -> 'outorgante_nome'\n"
            "- CPF/CNPJ (do proprietário) -> 'outorgante_documento'\n"
            "\n"
            "Exemplo de saída: "
            "{\"veiculo_renavam\": \"01234567890\", \"veiculo_placa\": \"AYR2H85\", ...}"
        )
        
        # 3. Prepara o arquivo PDF
        pdf_file.seek(0)
        pdf_data = pdf_file.read()

        # --- CORREÇÃO AQUI ---
        # Em vez de um dicionário, usamos o tipo 'Blob' da biblioteca.
        pdf_blob = genai_types.Blob(
            mime_type="application/pdf",
            data=pdf_data
        )
        # --- FIM DA CORREÇÃO ---
        
        # 4. Chama a API Gemini com o objeto Blob
        response = GEMINI_CLIENT.models.generate_content(
            model='gemini-1.5-flash-latest', 
            contents=[
                "Extraia os dados deste documento PDF.", 
                pdf_blob  # <-- Agora estamos passando o objeto Blob
            ],
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json"
            },
        )
        
        # 5. Processa a resposta
        cleaned_json = re.sub(r'```json\s*|\s*```', '', response.text, flags=re.DOTALL).strip()
        
        data = json.loads(cleaned_json)

        # 6. Lógica de pós-processamento
        if data.get('outorgante_documento'):
            doc_limpo = re.sub(r'\D', '', data['outorgante_documento'])
            if len(doc_limpo) > 11:
                data['tipo_documento'] = 'CNPJ'
            else:
                data['tipo_documento'] = 'CPF'
        
        return data

    except Exception as e:
        print(f"Erro ao processar PDF com Gemini: {e}")
        if 'response' in locals():
            print(f"Resposta recebida (se houver): {getattr(response, 'text', 'N/A')}")
        return None