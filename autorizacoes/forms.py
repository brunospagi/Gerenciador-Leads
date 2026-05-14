from decimal import Decimal, InvalidOperation

from django import forms

from .models import Autorizacao


class AutorizacaoForm(forms.ModelForm):
    class Meta:
        model = Autorizacao
        fields = ['placa', 'modelo', 'ano', 'cor', 'tipo', 'descricao', 'valor_estimado']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'placa': forms.TextInput(attrs={'style': 'text-transform:uppercase'}),
            'valor_estimado': forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'}),
        }

    def clean_valor_estimado(self):
        valor = self.cleaned_data.get('valor_estimado')
        if isinstance(valor, Decimal):
            return valor
        if valor in (None, ''):
            raise forms.ValidationError('Informe um valor estimado valido.')
        valor_str = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        try:
            return Decimal(valor_str)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Informe um valor estimado valido.')
