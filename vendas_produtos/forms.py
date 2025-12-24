from django import forms
from .models import VendaProduto

class VendaProdutoForm(forms.ModelForm):
    class Meta:
        model = VendaProduto
        fields = [
            'tipo_produto', 'cliente_nome', 'placa', 'valor_venda', 
            'forma_pagamento', 'comprovante', 'banco_financiamento', 
            'numero_proposta', 'custo_base', 'observacoes', 'data_venda'
        ]
        widgets = {
            'data_venda': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'placa': forms.TextInput(attrs={'style': 'text-transform:uppercase', 'class': 'form-control'}),
            'cliente_nome': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_venda': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'custo_base': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'tipo_produto': forms.Select(attrs={'class': 'form-select'}),
            'forma_pagamento': forms.Select(attrs={'class': 'form-select'}),
            'comprovante': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Campos condicionais começam ocultos ou desabilitados visualmente via JS
        self.fields['banco_financiamento'].required = False
        self.fields['numero_proposta'].required = False
        self.fields['comprovante'].required = False 
        # A validação real ocorre no clean() do Model