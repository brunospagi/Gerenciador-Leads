from django import forms
from .models import Avaliacao, AvaliacaoFoto

class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = ['placa', 'modelo', 'telefone', 'valor_pretendido', 'observacao', 'valor_avaliado']
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
        }

class AvaliacaoFotoForm(forms.ModelForm):
    class Meta:
        model = AvaliacaoFoto
        fields = ['foto']
        widgets = {
            # CORREÇÃO: Troque ClearableFileInput por FileInput para permitir múltiplos uploads
            'foto': forms.FileInput(attrs={'multiple': True})
        }