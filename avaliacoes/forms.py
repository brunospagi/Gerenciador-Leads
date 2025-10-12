from django import forms
from .models import Avaliacao

class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = ['placa', 'modelo', 'telefone', 'valor_pretendido', 'observacao', 'valor_avaliado']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
        }

# CORREÇÃO: Usar um forms.Form simples para o campo de múltiplos uploads
class FotoUploadForm(forms.Form):
    # Este campo não está ligado a nenhum modelo, apenas gerencia o input
    fotos = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'multiple': True,
            'class': 'form-control' # Adicionando uma classe para estilização
        })
    )