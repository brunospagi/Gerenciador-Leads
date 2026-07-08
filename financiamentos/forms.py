from django import forms
from decimal import Decimal
from core.money_utils import parse_valor_monetario
from .models import Ficha

_MONEY_WIDGET = forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'})


class FichaForm(forms.ModelForm):
    # CharField explícito (não o DecimalField que o ModelForm geraria
    # sozinho): o to_python() do DecimalField do Django rejeita valor com
    # vírgula antes de qualquer clean_<campo> customizado rodar, e a máscara
    # monetária sempre mostra vírgula (ex. "1.500,00").
    valor_veiculo = forms.CharField(label='Valor Veículo', widget=_MONEY_WIDGET)
    valor_financiado = forms.CharField(label='Valor Financiado', widget=_MONEY_WIDGET)
    valor_parcela = forms.CharField(label='Valor Parcela', widget=_MONEY_WIDGET)

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
            'banco': forms.TextInput(attrs={'class': 'form-control'}),
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control'}),
            'porcentagem_retorno': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    @staticmethod
    def _parse_money(value, field_label):
        if isinstance(value, Decimal):
            return value
        resultado = parse_valor_monetario(value)
        if resultado is None:
            raise forms.ValidationError(f'Informe um valor válido para {field_label}.')
        return resultado

    def clean_valor_veiculo(self):
        return self._parse_money(self.cleaned_data.get('valor_veiculo'), 'valor do veículo')

    def clean_valor_financiado(self):
        return self._parse_money(self.cleaned_data.get('valor_financiado'), 'valor financiado')

    def clean_valor_parcela(self):
        return self._parse_money(self.cleaned_data.get('valor_parcela'), 'valor da parcela')
