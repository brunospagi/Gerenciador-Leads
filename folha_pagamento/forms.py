from django import forms
from .models import Desconto, Credito, FolhaPagamento
from django.utils import timezone

class LancarDescontoForm(forms.ModelForm):
    class Meta:
        model = Desconto
        fields = ['funcionario', 'tipo', 'descricao', 'valor_total', 'parcelado', 'qtd_parcelas', 'mes_inicio', 'ano_inicio']
        widgets = {
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'mes_inicio': forms.NumberInput(attrs={'class': 'form-control'}),
            'ano_inicio': forms.NumberInput(attrs={'class': 'form-control'}),
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'funcionario': forms.Select(attrs={'class': 'form-control'}),
        }

class LancarCreditoForm(forms.ModelForm):
    class Meta:
        model = Credito
        fields = ['funcionario', 'tipo', 'descricao', 'valor_total', 'parcelado', 'qtd_parcelas', 'mes_inicio', 'ano_inicio']
        widgets = {
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'mes_inicio': forms.NumberInput(attrs={'class': 'form-control'}),
            'ano_inicio': forms.NumberInput(attrs={'class': 'form-control'}),
            'qtd_parcelas': forms.NumberInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'funcionario': forms.Select(attrs={'class': 'form-control'}),
        }

class ProcessarFolhaForm(forms.Form):
    mes = forms.IntegerField(label="Mês", initial=timezone.now().month, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    ano = forms.IntegerField(label="Ano", initial=timezone.now().year, widget=forms.NumberInput(attrs={'class': 'form-control'}))