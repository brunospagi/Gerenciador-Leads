from django import forms
from .models import RegistroPonto

class RegistroPontoForm(forms.ModelForm):
    class Meta:
        model = RegistroPonto
        fields = ['entrada', 'saida_almoco', 'retorno_almoco', 'saida']
        
        # Define os campos como inputs de hora nativos do HTML5
        widgets = {
            'entrada': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'saida_almoco': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'retorno_almoco': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'saida': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }