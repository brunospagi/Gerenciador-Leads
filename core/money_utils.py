import re
from decimal import Decimal, InvalidOperation


def parse_valor_monetario(valor_str):
    """
    Converte texto de um campo com máscara monetária para Decimal, aceitando
    tanto o formato BR completo ("1.500,00") quanto um decimal simples
    ("1500.00" ou "1500,00") — evita assumir um único formato, que causava
    valores inflados quando o texto chegava sem os separadores de milhar
    esperados (ex.: "1500.50" virando R$ 150.050,00).

    Retorna None se não for possível converter (chamador decide como tratar:
    erro de validação, ou None quando o campo é opcional).
    """
    if valor_str is None:
        return None
    s = re.sub(r'[^\d,.\-]', '', str(valor_str)).strip()
    if not s:
        return None
    if ',' in s:
        # Formato BR: 1.234.567,89 (ponto = milhar, vírgula = decimal)
        s = s.replace('.', '').replace(',', '.')
    else:
        # Só ponto(s): 1234567.89 (decimal) ou 1.234.567 (milhar sem centavos)
        if s.count('.') > 1:
            s = s.replace('.', '')
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None
