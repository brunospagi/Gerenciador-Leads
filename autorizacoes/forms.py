from decimal import Decimal

from django import forms

from core.money_utils import parse_valor_monetario
from .models import Autorizacao


class AutorizacaoForm(forms.ModelForm):
    # CharField explícito (não o DecimalField que o ModelForm geraria
    # sozinho): o to_python() do DecimalField do Django rejeita valor com
    # vírgula antes do clean_valor_estimado customizado rodar, e a máscara
    # monetária sempre mostra vírgula (ex. "1.500,00").
    valor_estimado = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'}))

    class Meta:
        model = Autorizacao
        fields = ['placa', 'modelo', 'ano', 'cor', 'tipo', 'descricao', 'valor_estimado']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'placa': forms.TextInput(attrs={'style': 'text-transform:uppercase'}),
        }

    def clean_valor_estimado(self):
        valor = self.cleaned_data.get('valor_estimado')
        if isinstance(valor, Decimal):
            return valor
        resultado = parse_valor_monetario(valor)
        if resultado is None:
            raise forms.ValidationError('Informe um valor estimado valido.')
        return resultado
