from django import forms
from .models import Avaliacao

class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = ['placa', 'modelo', 'telefone', 'valor_pretendido', 'observacao', 'valor_avaliado']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
        }

# CORREÇÃO DEFINITIVA: Simplifique o formulário ao máximo.
# A lógica de 'múltiplo' será tratada no template.
class FotoUploadForm(forms.Form):
    fotos = forms.ImageField(
        required=False,
        # Remova o widget daqui para evitar o erro do Django.
    )