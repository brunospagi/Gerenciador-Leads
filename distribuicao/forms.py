# distribuicao/forms.py
from django import forms
from clientes.models import Cliente

class LeadEntradaForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome_cliente', 'modelo_veiculo', 'whatsapp', 'fonte_cliente', 'observacao']
        widgets = {
            'nome_cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Cliente'}),
            'modelo_veiculo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Veículo de Interesse'}),
            'whatsapp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(XX) XXXXX-XXXX'}),
            'fonte_cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Instagram, Indicação'}),
            'observacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }