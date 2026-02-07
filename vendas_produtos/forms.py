from django import forms
from django.utils import timezone
from .models import VendaProduto, ParametrosComissao

# --- FORMULÁRIO DE CONFIGURAÇÃO (ADMIN) ---
class ParametrosComissaoForm(forms.ModelForm):
    class Meta:
        model = ParametrosComissao
        fields = '__all__'
        widgets = {
            'comissao_carro_padrao': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'comissao_carro_desconto': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'comissao_moto': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'comissao_consignacao': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'garantia_custo': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'garantia_base': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'seguro_novo_ref': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            
            # Splits
            'split_transferencia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'max': '1.0'}),
            'split_refin': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'max': '1.0'}),
            'split_ajudante': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'max': '1.0'}),
        }

# --- FORMULÁRIO DE VENDA (PADRÃO) ---
class VendaProdutoForm(forms.ModelForm):
    METODO_CHOICES = [
        ('', 'Selecione...'),
        ('pgto_pix', 'Pix'),
        ('pgto_transferencia', 'Transferência'),
        ('pgto_debito', 'Cartão de Débito'),
        ('pgto_credito', 'Cartão de Crédito'),
        ('pgto_financiamento', 'Incluso no Financiamento'),
    ]

    com_desconto = forms.TypedChoiceField(
        choices=[(False, 'Não'), (True, 'Sim')],
        coerce=lambda x: str(x).lower() == 'true',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Deu Desconto?",
        initial=False
    )

    # Adicionais
    adicional_garantia = forms.BooleanField(required=False, label="Incluir Seguro Garantia?")
    valor_garantia = forms.DecimalField(required=False, label="Valor (R$)", max_digits=10, decimal_places=2)
    metodo_garantia = forms.ChoiceField(required=False, choices=METODO_CHOICES, label="Pagamento")
    
    adicional_seguro = forms.BooleanField(required=False, label="Incluir Seguro Novo?")
    valor_seguro = forms.DecimalField(required=False, label="Valor (R$)", max_digits=10, decimal_places=2)
    metodo_seguro = forms.ChoiceField(required=False, choices=METODO_CHOICES, label="Pagamento")
    
    adicional_transferencia = forms.BooleanField(required=False, label="Incluir Transferência?")
    valor_transferencia = forms.DecimalField(required=False, label="Valor (R$)", max_digits=10, decimal_places=2)
    custo_transferencia = forms.DecimalField(required=False, label="Custo Despachante (R$)", max_digits=10, decimal_places=2, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm money-mask'}))
    metodo_transferencia = forms.ChoiceField(required=False, choices=METODO_CHOICES, label="Pagamento")

    class Meta:
        model = VendaProduto
        fields = [
            'tipo_produto', 'com_desconto', 'cliente_nome', 
            'modelo_veiculo', 'placa', 'cor', 'ano',
            'custo_base', 
            'valor_venda', 
            'qtd_parcelas', 'valor_parcela', 'valor_retorno_operacao',
            'pgto_pix', 'pgto_transferencia', 'pgto_debito', 'pgto_credito', 'pgto_financiamento',
            'comprovante', 'banco_financiamento', 
            'numero_proposta', 'observacoes', 'data_venda',
            'vendedor_ajudante' 
        ]
        widgets = {
            'data_venda': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'cliente_nome': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo_veiculo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Onix LTZ 1.4'}),
            'placa': forms.TextInput(attrs={'style': 'text-transform:uppercase', 'class': 'form-control'}),
            'cor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Prata'}),
            'ano': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 2023/2024'}),
            'tipo_produto': forms.Select(attrs={'class': 'form-select'}), 
            'custo_base': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'valor_venda': forms.TextInput(attrs={'class': 'form-control fw-bold fs-5 text-success money-mask'}),
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 48'}),
            'valor_parcela': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'valor_retorno_operacao': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'pgto_pix': forms.TextInput(attrs={'class': 'form-control payment-input money-mask'}),
            'pgto_transferencia': forms.TextInput(attrs={'class': 'form-control payment-input money-mask'}),
            'pgto_debito': forms.TextInput(attrs={'class': 'form-control payment-input money-mask'}),
            'pgto_credito': forms.TextInput(attrs={'class': 'form-control payment-input money-mask'}),
            'pgto_financiamento': forms.TextInput(attrs={'class': 'form-control payment-input money-mask'}),
            'observacoes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'comprovante': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'banco_financiamento': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_proposta': forms.TextInput(attrs={'class': 'form-control'}),
            'vendedor_ajudante': forms.Select(attrs={'class': 'form-select'}), 
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if 'data_venda' not in self.initial or not self.initial['data_venda']:
            self.initial['data_venda'] = timezone.now().date()
            
        self.fields['banco_financiamento'].required = False
        self.fields['numero_proposta'].required = False
        self.fields['comprovante'].required = False
        self.fields['modelo_veiculo'].required = False
        self.fields['cor'].required = False
        self.fields['ano'].required = False
        self.fields['custo_base'].required = False
        self.fields['qtd_parcelas'].required = False
        self.fields['valor_parcela'].required = False
        self.fields['valor_retorno_operacao'].required = False
        self.fields['vendedor_ajudante'].required = False
        self.fields['vendedor_ajudante'].label = "Teve ajuda? (Divide 50%)"

        for field in ['metodo_garantia', 'metodo_seguro', 'metodo_transferencia']:
            self.fields[field].widget.attrs.update({'class': 'form-select form-select-sm'})
        
        for field in ['valor_garantia', 'valor_seguro', 'valor_transferencia']:
            css_classes = self.fields[field].widget.attrs.get('class', '')
            self.fields[field].widget = forms.TextInput(attrs={'class': f'form-control form-control-sm money-mask {css_classes}'})

        # FILTRO DE OPÇÕES
        is_consignador = False
        if self.user:
            try:
                nivel = getattr(self.user.profile, 'nivel_acesso', '')
                if self.user.is_superuser or nivel == 'ADMIN' or nivel == 'CONSIGNADOR':
                    is_consignador = True
            except: pass
        
        if not is_consignador:
            novas_choices = [c for c in self.fields['tipo_produto'].choices if c[0] not in ['CONSIGNACAO', 'COMPRA']]
            self.fields['tipo_produto'].choices = novas_choices