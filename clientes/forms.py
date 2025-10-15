from django.contrib.auth.models import User
from django import forms
from .models import Cliente, Historico

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'whatsapp', 'nome_cliente',
            'marca_veiculo', 'modelo_veiculo', 'ano_veiculo', 'valor_estimado_veiculo',
            'fonte_cliente', 'quantidade_ligacoes', 'tipo_negociacao', 'tipo_contato',
            'status_negociacao', 'proximo_passo', 'prioridade', 'observacao', 'vendedor',
            'data_proximo_contato' # Adicionado para controle
        ]
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
            'whatsapp': forms.TextInput(attrs={'placeholder': '(99) 9 9999-9999'}),
            'valor_estimado_veiculo': forms.TextInput(attrs={'placeholder': 'R$ 0,00'}),
            'marca_veiculo': forms.HiddenInput(),
            'modelo_veiculo': forms.HiddenInput(),
            'ano_veiculo': forms.HiddenInput(),
            'data_proximo_contato': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

        if user and not user.is_superuser:
            self.fields['vendedor'].disabled = True
            self.fields['vendedor'].required = False

class HistoricoForm(forms.ModelForm):
    class Meta:
        model = Historico
        fields = ['motivacao']
        widgets = {
            'motivacao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva a nova interação...'}),
        }