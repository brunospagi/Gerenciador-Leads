import pdfplumber
import re
from io import BytesIO

def extract_crlv_data(pdf_file):
    """
    Extrai dados de um arquivo PDF CRLV-e (como o arquivo de exemplo).
    """
    text = ""
    try:
        # Abre o arquivo PDF (seja do upload ou um caminho)
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                # Extrai o texto da página, mantendo a formatação
                page_text = page.extract_text(layout=True, use_text_flow=True)
                if page_text:
                    text += page_text + "\n"
                    
    except Exception as e:
        print(f"Erro ao ler o PDF: {e}")
        return None

    if not text:
        print("Nenhum texto extraído do PDF.")
        return None

    data = {}
    
    # Padrões de Regex para encontrar os campos-chave.
    # Estes padrões buscam o "Rótulo" e capturam o "Valor" que vem logo após,
    # geralmente na linha seguinte.
    patterns = {
        'veiculo_placa': r'PLACA\n([A-Z0-9]+)',
        'veiculo_renavam': r'CÓDIGO RENAVAM\n(\d+)',
        'veiculo_marca_modelo': r'MARCA/MODELO/VERSÃO\n(.+)',
        'veiculo_ano_fab': r'ANO FABRICAÇÃO\n(\d{4})',
        'veiculo_ano_mod': r'ANO MODELO\n(\d{4})',
        'veiculo_cor': r'COR PREDOMINANTE\n([A-ZÁ-Ú]+)',
        'veiculo_renavam_alt': r'RENAVAM\n(\d+)', # Padrão alternativo (às vezes o rótulo é só RENAVAM)
        'outorgante_nome': r'NOME\n([A-ZÁ-Ú\s]+)\nCPF/CNPJ', # Pega o NOME que está acima do CPF/CNPJ
        'outorgante_documento': r'CPF/CNPJ\n([\d.-/]+)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            extracted_value = match.group(1).strip()
            
            # Limpeza para MARCA/MODELO
            if key == 'veiculo_marca_modelo':
                # Remove lixo que pode ser capturado após o nome
                extracted_value = re.sub(r'ASSINADO DIGITALMENTE.*', '', extracted_value, flags=re.IGNORECASE).strip()
            
            # Evita sobrescrever se já encontrou (ex: renavam)
            if key == 'veiculo_renavam_alt' and 'veiculo_renavam' not in data:
                 data['veiculo_renavam'] = extracted_value
            elif 'alt' not in key:
                data[key] = extracted_value

    # Lógica para definir o tipo de documento (CPF/CNPJ)
    if data.get('outorgante_documento'):
        doc_limpo = re.sub(r'\D', '', data['outorgante_documento'])
        if len(doc_limpo) > 11:
            data['tipo_documento'] = 'CNPJ'
        else:
            data['tipo_documento'] = 'CPF'
            
    return data