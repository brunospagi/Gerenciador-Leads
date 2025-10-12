# brunospagi/gerenciador-leads/Gerenciador-Leads-fecd02772f93afa4ca06347c8334383a86eb8295/avaliacoes/forms.py

from django import forms
from .models import Avaliacao

class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        # Atualize os campos para incluir os novos
        fields = ['marca', 'modelo', 'ano', 'placa', 'telefone', 'valor_pretendido', 'observacao', 'valor_avaliado']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
            # Esconde os campos que serão preenchidos pela API via JavaScript
            'marca': forms.HiddenInput(),
            'modelo': forms.HiddenInput(),
            'ano': forms.HiddenInput(),
        }

class FotoUploadForm(forms.Form):
    fotos = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'multiple': True,
            'class': 'form-control'
        })
    )