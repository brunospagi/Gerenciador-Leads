from django import forms
from .models import TransacaoFinanceira

class TransacaoFinanceiraForm(forms.ModelForm):
    class Meta:
        model = TransacaoFinanceira
        fields = '__all__'
        widgets = {
            'data_vencimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_pagamento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'placa': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo_veiculo': forms.TextInput(attrs={'class': 'form-control'}),
            'ano': forms.TextInput(attrs={'class': 'form-control'}),
        }