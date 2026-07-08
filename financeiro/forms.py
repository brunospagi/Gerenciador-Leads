from django import forms
from decimal import Decimal
from django.utils import timezone
from core.money_utils import parse_valor_monetario
from .models import TransacaoFinanceira

class TransacaoFinanceiraForm(forms.ModelForm):
    # CharField explícito (não o DecimalField que o ModelForm geraria
    # sozinho): o to_python() do DecimalField do Django rejeita valor com
    # vírgula antes do clean_valor customizado rodar, e a máscara monetária
    # sempre mostra vírgula (ex. "1.500,00").
    valor = forms.CharField(label='Valor', widget=forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'}))

    class Meta:
        model = TransacaoFinanceira
        fields = '__all__'
        widgets = {
            'data_vencimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_pagamento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'placa': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo_veiculo': forms.TextInput(attrs={'class': 'form-control'}),
            'ano': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_valor(self):
        valor = self.cleaned_data.get('valor')
        if isinstance(valor, Decimal):
            return valor
        resultado = parse_valor_monetario(valor)
        if resultado is None:
            raise forms.ValidationError('Informe um valor válido.')
        return resultado

    def clean(self):
        cleaned_data = super().clean()
        # Mesma regra que a ação em lote de "marcar efetivado"/"marcar
        # pendente" já aplica (financeiro/views.py) — sem isso, dava pra
        # marcar efetivado sem data_pagamento pelo formulário e a transação
        # sumia silenciosamente do DRE (que filtra por data_pagamento).
        if cleaned_data.get('efetivado') and not cleaned_data.get('data_pagamento'):
            cleaned_data['data_pagamento'] = timezone.localdate()
        elif not cleaned_data.get('efetivado'):
            cleaned_data['data_pagamento'] = None
        return cleaned_data
