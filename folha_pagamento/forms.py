from decimal import Decimal, InvalidOperation

from django import forms
from .models import Desconto, Credito, FolhaPagamento
from django.utils import timezone

class _ValorMonetarioMixin:
    def clean_valor_total(self):
        valor = self.cleaned_data.get('valor_total')
        if isinstance(valor, Decimal):
            return valor
        if valor in (None, ''):
            raise forms.ValidationError('Informe um valor total vÃ¡lido.')
        valor_str = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        try:
            return Decimal(valor_str)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Informe um valor total vÃ¡lido.')


    def clean(self):
        cleaned_data = super().clean()
        parcelado = cleaned_data.get('parcelado')
        qtd_parcelas = cleaned_data.get('qtd_parcelas') or 1
        mes_inicio = cleaned_data.get('mes_inicio')
        ano_inicio = cleaned_data.get('ano_inicio')

        if not parcelado:
            cleaned_data['qtd_parcelas'] = 1
        elif qtd_parcelas < 1:
            self.add_error('qtd_parcelas', 'Informe pelo menos 1 parcela.')

        if mes_inicio and not 1 <= mes_inicio <= 12:
            self.add_error('mes_inicio', 'Informe um mes entre 1 e 12.')

        if ano_inicio and ano_inicio < 2000:
            self.add_error('ano_inicio', 'Informe um ano valido.')

        return cleaned_data


class LancarDescontoForm(_ValorMonetarioMixin, forms.ModelForm):
    class Meta:
        model = Desconto
        fields = ['funcionario', 'tipo', 'descricao', 'valor_total', 'parcelado', 'qtd_parcelas', 'mes_inicio', 'ano_inicio']
        widgets = {
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_total': forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'}),
            'mes_inicio': forms.NumberInput(attrs={'class': 'form-control'}),
            'ano_inicio': forms.NumberInput(attrs={'class': 'form-control'}),
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'funcionario': forms.Select(attrs={'class': 'form-control'}),
        }

class LancarCreditoForm(_ValorMonetarioMixin, forms.ModelForm):
    class Meta:
        model = Credito
        fields = ['funcionario', 'tipo', 'descricao', 'valor_total', 'parcelado', 'qtd_parcelas', 'mes_inicio', 'ano_inicio']
        widgets = {
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_total': forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'}),
            'mes_inicio': forms.NumberInput(attrs={'class': 'form-control'}),
            'ano_inicio': forms.NumberInput(attrs={'class': 'form-control'}),
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'funcionario': forms.Select(attrs={'class': 'form-control'}),
        }

class ProcessarFolhaForm(forms.Form):
    mes = forms.IntegerField(label="MÃªs", initial=timezone.now().month, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    ano = forms.IntegerField(label="Ano", initial=timezone.now().year, widget=forms.NumberInput(attrs={'class': 'form-control'}))
