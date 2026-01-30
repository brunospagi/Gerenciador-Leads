from django import forms
from django.utils import timezone
from .models import VendaProduto

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

    # --- ADICIONAIS ---
    adicional_garantia = forms.BooleanField(required=False, label="Incluir Seguro Garantia?")
    valor_garantia = forms.DecimalField(required=False, label="Valor (R$)", max_digits=10, decimal_places=2)
    metodo_garantia = forms.ChoiceField(required=False, choices=METODO_CHOICES, label="Pagamento")
    
    adicional_seguro = forms.BooleanField(required=False, label="Incluir Seguro Novo?")
    valor_seguro = forms.DecimalField(required=False, label="Valor (R$)", max_digits=10, decimal_places=2)
    metodo_seguro = forms.ChoiceField(required=False, choices=METODO_CHOICES, label="Pagamento")
    
    adicional_transferencia = forms.BooleanField(required=False, label="Incluir Transferência?")
    valor_transferencia = forms.DecimalField(required=False, label="Valor (R$)", max_digits=10, decimal_places=2)
    
    custo_transferencia = forms.DecimalField(
        required=False, 
        label="Custo Despachante (R$)", 
        max_digits=10, 
        decimal_places=2,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm money-mask'})
    )
    
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
            
            # Mudança: NumberInput -> TextInput e adição da classe money-mask
            'custo_base': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            
            'valor_venda': forms.TextInput(attrs={'class': 'form-control fw-bold fs-5 text-success money-mask'}),
            
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 48'}),
            
            # Mudança: NumberInput -> TextInput e adição da classe money-mask
            'valor_parcela': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'valor_retorno_operacao': forms.TextInput(attrs={'class': 'form-control money-mask'}),

            # Pagamentos
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

        # Config Helper
        self.fields['vendedor_ajudante'].required = False
        self.fields['vendedor_ajudante'].label = "Teve ajuda? (Divide 50%)"

        for field in ['metodo_garantia', 'metodo_seguro', 'metodo_transferencia']:
            self.fields[field].widget.attrs.update({'class': 'form-select form-select-sm'})
        
        # Adicionar money-mask aos campos de valores extras
        for field in ['valor_garantia', 'valor_seguro', 'valor_transferencia']:
            css_classes = self.fields[field].widget.attrs.get('class', '')
            self.fields[field].widget = forms.TextInput(attrs={'class': f'form-control form-control-sm money-mask {css_classes}'})