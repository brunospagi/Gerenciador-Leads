from django import forms
from .models import Desconto

class LancarDescontoForm(forms.ModelForm):
    class Meta:
        model = Desconto
        fields = ['funcionario', 'tipo', 'descricao', 'valor_total', 'parcelado', 'qtd_parcelas', 'mes_inicio', 'ano_inicio']
        widgets = {
            'funcionario': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_total': forms.TextInput(attrs={'class': 'form-control money-mask'}),
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control', 'value': 1}),
            'mes_inicio': forms.NumberInput(attrs={'class': 'form-control'}),
            'ano_inicio': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class ProcessarFolhaForm(forms.Form):
    mes = forms.IntegerField(min_value=1, max_value=12, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Mês (ex: 5)'}))
    ano = forms.IntegerField(widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ano (ex: 2024)'}))