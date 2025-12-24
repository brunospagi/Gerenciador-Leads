from django import forms
from django.utils import timezone
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
            # OBRIGATÓRIO: format='%Y-%m-%d' faz o navegador reconhecer a data vinda do banco
            'data_venda': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'placa': forms.TextInput(attrs={'style': 'text-transform:uppercase', 'class': 'form-control'}),
            'cliente_nome': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_venda': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'custo_base': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'tipo_produto': forms.Select(attrs={'class': 'form-select'}),
            'forma_pagamento': forms.Select(attrs={'class': 'form-select'}),
            'comprovante': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'banco_financiamento': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_proposta': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Define Data Inicial se estiver vazia (Dia de Hoje)
        if 'data_venda' not in self.initial or not self.initial['data_venda']:
            self.initial['data_venda'] = timezone.now().date()

        # 2. Desativa validação HTML padrão do Django para campos condicionais.
        # A validação real ocorre no método clean() do Model.
        self.fields['banco_financiamento'].required = False
        self.fields['numero_proposta'].required = False
        self.fields['comprovante'].required = False