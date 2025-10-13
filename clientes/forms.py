from django.contrib.auth.models import User
from django import forms
from .models import Cliente, Historico

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        # Esta lista de campos está correta. Ela inclui o novo campo 'marca_veiculo'.
        fields = [
            'whatsapp', 'nome_cliente',
            'marca_veiculo', 'modelo_veiculo', 'valor_estimado_veiculo',
            'fonte_cliente', 'quantidade_ligacoes', 'tipo_negociacao', 'tipo_contato',
            'status_negociacao', 'proximo_passo', 'prioridade', 'observacao', 'vendedor'
        ]
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
            'whatsapp': forms.TextInput(attrs={'placeholder': '(99) 9 9999-9999'}),
            'valor_estimado_veiculo': forms.TextInput(attrs={'placeholder': 'R$ 0,00'}),
            # Estes campos são preenchidos pelo JavaScript da FIPE
            'marca_veiculo': forms.HiddenInput(),
            'modelo_veiculo': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Aplica a classe de estilo a todos os campos
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

        # Lógica para desabilitar o campo de vendedor para usuários não-admins
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