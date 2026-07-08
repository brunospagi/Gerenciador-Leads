from decimal import Decimal
from django import forms
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.money_utils import parse_valor_monetario
from .models import VendaProduto, ParametrosComissao

User = get_user_model()
TIPOS_CUSTO_ADMIN = {'VENDA_VEICULO', 'VENDA_MOTO', 'CONSIGNACAO', 'COMPRA'}

_MONEY_WIDGET = forms.TextInput(attrs={'class': 'form-control money-mask'})


class _CamposMonetariosMixin:
    """
    Converte os campos listados em CAMPOS_MONETARIOS de texto mascarado
    ("1.500,00") para Decimal. Precisa rodar em clean() (não em clean_<campo>
    individual) porque esses campos são declarados como CharField em cada
    subclasse — colocar a lógica aqui, num mixin comum, é seguro pois clean()
    é só um método normal (a restrição de não poder declarar os Field em
    mixin vale só para os atributos Field, não para métodos).
    """
    CAMPOS_MONETARIOS = []
    CAMPOS_MONETARIOS_OPCIONAIS = []

    def _limpar_campos_monetarios(self, cleaned_data):
        for campo in self.CAMPOS_MONETARIOS:
            valor = cleaned_data.get(campo)
            if isinstance(valor, Decimal):
                continue
            if valor in (None, ''):
                if campo in self.CAMPOS_MONETARIOS_OPCIONAIS:
                    cleaned_data[campo] = Decimal('0.00')
                    continue
                self.add_error(campo, 'Informe um valor válido.')
                continue
            resultado = parse_valor_monetario(valor)
            if resultado is None:
                self.add_error(campo, 'Informe um valor válido.')
            else:
                cleaned_data[campo] = resultado
        return cleaned_data


# --- FORMULÁRIO DE CONFIGURAÇÃO (ADMIN) ---
class ParametrosComissaoForm(_CamposMonetariosMixin, forms.ModelForm):
    CAMPOS_MONETARIOS = [
        'comissao_carro_padrao', 'comissao_carro_desconto', 'comissao_moto',
        'comissao_consignacao', 'garantia_custo', 'garantia_base', 'seguro_novo_ref',
    ]

    comissao_carro_padrao = forms.CharField(widget=_MONEY_WIDGET)
    comissao_carro_desconto = forms.CharField(widget=_MONEY_WIDGET)
    comissao_moto = forms.CharField(widget=_MONEY_WIDGET)
    comissao_consignacao = forms.CharField(widget=_MONEY_WIDGET)
    garantia_custo = forms.CharField(widget=_MONEY_WIDGET)
    garantia_base = forms.CharField(widget=_MONEY_WIDGET)
    seguro_novo_ref = forms.CharField(widget=_MONEY_WIDGET)

    class Meta:
        model = ParametrosComissao
        fields = '__all__'
        widgets = {
            # Splits
            'split_transferencia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'max': '1.0'}),
            'split_refin': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'max': '1.0'}),
            'split_ajudante': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'max': '1.0'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        return self._limpar_campos_monetarios(cleaned_data)

# --- FORMULÁRIO DE VENDA (PADRÃO) ---
class VendaProdutoForm(_CamposMonetariosMixin, forms.ModelForm):
    METODO_CHOICES = [
        ('', 'Selecione...'),
        ('pgto_pix', 'Pix'),
        ('pgto_transferencia', 'Transferência'),
        ('pgto_debito', 'Cartão de Débito'),
        ('pgto_credito', 'Cartão de Crédito'),
        ('pgto_financiamento', 'Incluso no Financiamento'),
    ]

    # Todos precisam ser CharField (não o DecimalField que o ModelForm
    # geraria sozinho, nem forms.DecimalField declarado direto): o to_python()
    # do DecimalField do Django rejeita valor com vírgula antes de qualquer
    # limpeza customizada rodar, e a máscara monetária sempre mostra vírgula.
    CAMPOS_MONETARIOS = [
        'custo_base', 'valor_venda', 'valor_parcela', 'valor_retorno_operacao',
        'pgto_pix', 'pgto_transferencia', 'pgto_debito', 'pgto_credito', 'pgto_financiamento',
        'valor_garantia', 'valor_seguro', 'valor_transferencia', 'custo_transferencia',
    ]
    CAMPOS_MONETARIOS_OPCIONAIS = [
        'custo_base', 'valor_parcela', 'valor_retorno_operacao',
        'pgto_pix', 'pgto_transferencia', 'pgto_debito', 'pgto_credito', 'pgto_financiamento',
        'valor_garantia', 'valor_seguro', 'valor_transferencia', 'custo_transferencia',
    ]

    custo_base = forms.CharField(required=False, widget=_MONEY_WIDGET)
    valor_venda = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control fw-bold fs-5 text-success money-mask'}))
    valor_parcela = forms.CharField(required=False, widget=_MONEY_WIDGET)
    valor_retorno_operacao = forms.CharField(required=False, widget=_MONEY_WIDGET)
    pgto_pix = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control payment-input money-mask'}))
    pgto_transferencia = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control payment-input money-mask'}))
    pgto_debito = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control payment-input money-mask'}))
    pgto_credito = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control payment-input money-mask'}))
    pgto_financiamento = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control payment-input money-mask'}))

    com_desconto = forms.TypedChoiceField(
        choices=[(False, 'Não'), (True, 'Sim')],
        coerce=lambda x: str(x).lower() == 'true',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Deu Desconto?",
        initial=False
    )

    # Adicionais
    _MONEY_WIDGET_SM = forms.TextInput(attrs={'class': 'form-control form-control-sm money-mask'})

    adicional_garantia = forms.BooleanField(required=False, label="Incluir Seguro Garantia?")
    valor_garantia = forms.CharField(required=False, label="Valor (R$)", widget=_MONEY_WIDGET_SM)
    metodo_garantia = forms.ChoiceField(required=False, choices=METODO_CHOICES, label="Pagamento")

    adicional_seguro = forms.BooleanField(required=False, label="Incluir Seguro Novo?")
    valor_seguro = forms.CharField(required=False, label="Valor (R$)", widget=_MONEY_WIDGET_SM)
    metodo_seguro = forms.ChoiceField(required=False, choices=METODO_CHOICES, label="Pagamento")

    adicional_transferencia = forms.BooleanField(required=False, label="Incluir Transferência?")
    valor_transferencia = forms.CharField(required=False, label="Valor (R$)", widget=_MONEY_WIDGET_SM)
    custo_transferencia = forms.CharField(required=False, label="Custo Despachante (R$)", widget=_MONEY_WIDGET_SM)
    metodo_transferencia = forms.ChoiceField(required=False, choices=METODO_CHOICES, label="Pagamento")

    class Meta:
        model = VendaProduto
        # Incluímos 'vendedor' na lista de campos possíveis
        fields = [
            'vendedor', 'tipo_produto', 'com_desconto', 'cliente_nome', 'origem_cliente',
            'dtnasc_cliente', 'rgIE_cliente', 'telCel_cliente', 'cpfCNPJ_cliente',
            'endereco_cliente', 'numero_cliente', 'cep_cliente', 'bairro_cliente', 'cidade_com_cliente',
            'marca_veiculo', 'modelo_veiculo', 'placa', 'cor', 'ano', 'km_veiculo',
            'custo_base', 
            'valor_venda', 
            'qtd_parcelas', 'valor_parcela', 'valor_retorno_operacao',
            'pgto_pix', 'pgto_transferencia', 'pgto_debito', 'pgto_credito', 'pgto_financiamento',
            'comprovante', 'banco_financiamento', 
            'numero_proposta', 'data_compra', 'documentacao_veiculo', 'observacoes', 'data_venda',
            'vendedor_ajudante' 
        ]
        widgets = {
            # Widget especial para o admin selecionar o vendedor
            'vendedor': forms.Select(attrs={'class': 'form-select fw-bold border-danger text-danger'}),
            
            'data_venda': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'cliente_nome': forms.TextInput(attrs={'class': 'form-control'}),
            'dtnasc_cliente': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'rgIE_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'telCel_cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000', 'maxlength': '15'}),
            'cpfCNPJ_cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '000.000.000-00', 'maxlength': '18'}),
            'endereco_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'cep_cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000-000', 'maxlength': '9'}),
            'bairro_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'cidade_com_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'origem_cliente': forms.Select(attrs={'class': 'form-select'}),
            'marca_veiculo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Chevrolet'}),
            'modelo_veiculo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Onix LTZ 1.4'}),
            'placa': forms.TextInput(attrs={'style': 'text-transform:uppercase', 'class': 'form-control'}),
            'cor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Prata'}),
            'ano': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 2023/2024'}),
            'km_veiculo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 65000'}),
            'tipo_produto': forms.Select(attrs={'class': 'form-select'}),
            # custo_base, valor_venda, valor_parcela, valor_retorno_operacao e os
            # pgto_* são declarados explicitamente como CharField acima (com seus
            # próprios widgets) — não entram aqui.
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 48'}),
            'observacoes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'comprovante': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'banco_financiamento': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_proposta': forms.TextInput(attrs={'class': 'form-control'}),
            'data_compra': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'documentacao_veiculo': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva a situação da documentação do veículo'}),
            'vendedor_ajudante': forms.Select(attrs={'class': 'form-select'}), 
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.is_admin = False
        super().__init__(*args, **kwargs)

        if 'data_venda' not in self.initial or not self.initial['data_venda']:
            self.initial['data_venda'] = timezone.now().date()
        if 'data_compra' not in self.initial or not self.initial['data_compra']:
            self.initial['data_compra'] = timezone.now().date()
            
        self.fields['banco_financiamento'].required = False
        self.fields['numero_proposta'].required = False
        self.fields['comprovante'].required = False
        self.fields['dtnasc_cliente'].required = False
        self.fields['rgIE_cliente'].required = False
        self.fields['telCel_cliente'].required = False
        self.fields['cpfCNPJ_cliente'].required = False
        self.fields['endereco_cliente'].required = False
        self.fields['numero_cliente'].required = False
        self.fields['cep_cliente'].required = False
        self.fields['bairro_cliente'].required = False
        self.fields['cidade_com_cliente'].required = False
        self.fields['marca_veiculo'].required = False
        self.fields['modelo_veiculo'].required = False
        self.fields['cor'].required = False
        self.fields['ano'].required = False
        self.fields['km_veiculo'].required = False
        self.fields['custo_base'].required = False
        self.fields['qtd_parcelas'].required = False
        self.fields['valor_parcela'].required = False
        self.fields['valor_retorno_operacao'].required = False
        self.fields['data_compra'].required = False
        self.fields['documentacao_veiculo'].required = False
        self.fields['vendedor_ajudante'].required = False
        self.fields['vendedor_ajudante'].label = "Teve ajuda? (Divide 50%)"

        for field in ['metodo_garantia', 'metodo_seguro', 'metodo_transferencia']:
            self.fields[field].widget.attrs.update({'class': 'form-select form-select-sm'})

        # --- LÓGICA DE PERMISSÃO: ADMIN VÊ CAMPO VENDEDOR ---
        is_admin = False
        is_consignador = False
        
        if self.user:
            try:
                nivel = getattr(self.user.profile, 'nivel_acesso', '')
                if self.user.is_superuser or nivel == 'ADMIN':
                    is_admin = True
                if self.user.is_superuser or nivel == 'ADMIN' or nivel == 'CONSIGNADOR':
                    is_consignador = True
            except: pass
        
        # Se for ADMIN, configura o campo vendedor para aparecer
        if is_admin:
            self.fields['vendedor'].required = True
            self.fields['vendedor'].label = "VENDEDOR (LANÇAMENTO ADMINISTRATIVO)"
            # Carrega todos os usuários ativos
            self.fields['vendedor'].queryset = User.objects.filter(is_active=True).order_by('username')
            # Se for uma nova venda, já deixa o Admin selecionado por padrão para facilitar
            if not self.instance.pk:
                self.fields['vendedor'].initial = self.user
        else:
            # Se não for admin, removemos o campo do formulário para evitar erros
            if 'vendedor' in self.fields:
                del self.fields['vendedor']

        if not is_consignador:
            novas_choices = [c for c in self.fields['tipo_produto'].choices if c[0] not in ['CONSIGNACAO', 'COMPRA']]
            self.fields['tipo_produto'].choices = novas_choices

        self.is_admin = is_admin

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data = self._limpar_campos_monetarios(cleaned_data)
        tipo = cleaned_data.get('tipo_produto') or getattr(self.instance, 'tipo_produto', None)

        # Defesa em profundidade: custo de veículo só pode ser definido por ADMIN.
        if (not self.is_admin) and tipo in TIPOS_CUSTO_ADMIN:
            if self.instance and self.instance.pk:
                cleaned_data['custo_base'] = self.instance.custo_base
            else:
                cleaned_data['custo_base'] = Decimal('0.00')

        return cleaned_data
