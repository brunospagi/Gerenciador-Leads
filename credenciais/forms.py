from django import forms
from .models import Credencial

class CredencialForm(forms.ModelForm):
    class Meta:
        model = Credencial
        fields = ['nome', 'link', 'usuario', 'senha', 'observacao']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Banco Santander'}),
            'link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'usuario': forms.TextInput(attrs={'class': 'form-control'}),
            'senha': forms.TextInput(attrs={'class': 'form-control fw-bold text-danger'}), 
            'observacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ex: Token físico na gaveta...'}),
        }