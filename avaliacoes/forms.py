from django import forms
from .models import Avaliacao

class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        # Atualize os campos para incluir os novos
        fields = ['tipo_veiculo', 'marca', 'modelo', 'ano', 'placa', 'telefone', 'valor_pretendido', 'observacao', 'valor_avaliado']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
            # Esconde os campos que serão preenchidos pela API via JavaScript
            'marca': forms.HiddenInput(),
            'modelo': forms.HiddenInput(),
            'ano': forms.HiddenInput(),
        }

# CORREÇÃO DEFINITIVA: Simplifique o formulário ao máximo.
# A lógica de 'múltiplo' será tratada no template.
class FotoUploadForm(forms.Form):
    fotos = forms.ImageField(
        required=False,
        # Remova o widget daqui para evitar o erro do Django.
    )