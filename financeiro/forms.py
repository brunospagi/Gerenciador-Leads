from django import forms
from decimal import Decimal, InvalidOperation
from .models import TransacaoFinanceira

class TransacaoFinanceiraForm(forms.ModelForm):
    class Meta:
        model = TransacaoFinanceira
        fields = '__all__'
        widgets = {
            'data_vencimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_pagamento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'}),
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
        if valor in (None, ''):
            raise forms.ValidationError('Informe um valor válido.')
        valor_str = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        try:
            return Decimal(valor_str)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Informe um valor válido.')
