from django import forms
from .models import VendaProduto

class VendaProdutoForm(forms.ModelForm):
    cobrou_adesao = forms.ChoiceField(
        choices=[('SIM', 'Sim, cobrou adesão'), ('NAO', 'Não cobrou (R$ 0,00)')],
        required=False,
        label="Houve cobrança de adesão?",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'cobrouAdesaoSelect'})
    )

    class Meta:
        model = VendaProduto
        fields = [
            'tipo_produto', 'placa', 'cliente_nome', 
            'valor_venda', 'custo_base', 'forma_pagamento',
            'comprovante', 'banco_financiamento', 'numero_proposta',
            'observacoes'
        ]
        widgets = {
            'tipo_produto': forms.Select(attrs={'class': 'form-select', 'id': 'tipoProdutoSelect'}),
            'placa': forms.TextInput(attrs={'style': 'text-transform:uppercase', 'class': 'form-control'}),
            'cliente_nome': forms.TextInput(attrs={'class': 'form-control'}),
            
            'valor_venda': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'valorVendaInput'}),
            'custo_base': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'custoBaseInput'}),
            
            # Novos Campos
            'forma_pagamento': forms.Select(attrs={'class': 'form-select', 'id': 'formaPagamentoSelect'}),
            'comprovante': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'comprovanteInput'}),
            'banco_financiamento': forms.TextInput(attrs={'class': 'form-control', 'id': 'bancoInput'}),
            'numero_proposta': forms.TextInput(attrs={'class': 'form-control', 'id': 'propostaInput'}),
            
            'observacoes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['custo_base'].label = "Custo (Despachante)"