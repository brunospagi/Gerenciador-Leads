from django import forms
from .models import RegistroPonto

class RegistroPontoForm(forms.ModelForm):
    class Meta:
        model = RegistroPonto
        fields = [
            'entrada',
            'saida_almoco',
            'retorno_almoco',
            'saida',
            'atraso_minutos',
            'justificativa_atraso',
            'status_homologacao',
            'observacao_homologacao',
        ]
        
        # Define os campos como inputs de hora nativos do HTML5
        widgets = {
            'entrada': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'saida_almoco': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'retorno_almoco': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'saida': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'atraso_minutos': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'justificativa_atraso': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status_homologacao': forms.Select(attrs={'class': 'form-select'}),
            'observacao_homologacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
