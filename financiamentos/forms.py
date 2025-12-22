from django import forms
from .models import Ficha

class FichaForm(forms.ModelForm):
    class Meta:
        model = Ficha
        fields = [
            'cliente_nome', 'veiculo', 'ano', 'placa', 'valor_veiculo',
            'banco', 'valor_financiado', 'qtd_parcelas', 'valor_parcela',
            'porcentagem_retorno', 'status'
        ]
        widgets = {
            'cliente_nome': forms.TextInput(attrs={'class': 'form-control'}),
            'veiculo': forms.TextInput(attrs={'class': 'form-control'}),
            'ano': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 2018/2019'}),
            'placa': forms.TextInput(attrs={'class': 'form-control', 'style': 'text-transform:uppercase'}),
            'valor_veiculo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'banco': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_financiado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control'}),
            'valor_parcela': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'porcentagem_retorno': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }