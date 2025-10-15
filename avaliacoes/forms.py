from django import forms
from .models import Avaliacao

class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = ['tipo_veiculo', 'marca', 'modelo', 'ano', 'placa', 'telefone', 'valor_pretendido', 'observacao', 'valor_avaliado']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
            'marca': forms.HiddenInput(),
            'modelo': forms.HiddenInput(),
            'ano': forms.HiddenInput(),
            'valor_pretendido': forms.TextInput(attrs={'placeholder': 'R$ 0,00'}),
            'valor_avaliado': forms.TextInput(attrs={'placeholder': 'R$ 0,00'}),
        }

class FotoUploadForm(forms.Form):
    fotos = forms.ImageField(
        required=False,
    )