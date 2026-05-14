from django import forms
from decimal import Decimal, InvalidOperation
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
            'valor_veiculo': forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'}),
            'banco': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_financiado': forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'}),
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control'}),
            'valor_parcela': forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'}),
            'porcentagem_retorno': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    @staticmethod
    def _parse_money(value, field_label):
        if isinstance(value, Decimal):
            return value
        if value in (None, ''):
            raise forms.ValidationError(f'Informe um valor válido para {field_label}.')
        valor_str = str(value).replace('R$', '').replace('.', '').replace(',', '.').strip()
        try:
            return Decimal(valor_str)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError(f'Informe um valor válido para {field_label}.')

    def clean_valor_veiculo(self):
        return self._parse_money(self.cleaned_data.get('valor_veiculo'), 'valor do veículo')

    def clean_valor_financiado(self):
        return self._parse_money(self.cleaned_data.get('valor_financiado'), 'valor financiado')

    def clean_valor_parcela(self):
        return self._parse_money(self.cleaned_data.get('valor_parcela'), 'valor da parcela')
