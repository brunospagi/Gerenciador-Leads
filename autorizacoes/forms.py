from django import forms
from .models import Autorizacao

class AutorizacaoForm(forms.ModelForm):
    class Meta:
        model = Autorizacao
        fields = ['placa', 'modelo', 'ano', 'cor', 'tipo', 'descricao', 'valor_estimado']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'placa': forms.TextInput(attrs={'style': 'text-transform:uppercase'}),
        }
    
    # Aqui você pode adicionar lógica para buscar na API FIPE se quiser validar no Backend,
    # mas geralmente o preenchimento automático via JS no frontend é mais fluido.