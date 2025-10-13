from django import forms # type: ignore
from .models import Cliente
from django.contrib.auth.models import User # type: ignore

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'whatsapp', 'nome_cliente', 'modelo_veiculo', 'valor_estimado_veiculo',
            'fonte_cliente', 'quantidade_ligacoes', 'tipo_negociacao', 'tipo_contato',
            'status_negociacao', 'proximo_passo', 'prioridade', 'observacao'
        ]
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
            'whatsapp': forms.TextInput(attrs={'placeholder': '(99) 9 9999-9999'}),
            'valor_estimado_veiculo': forms.TextInput(attrs={'placeholder': 'R$ 0,00'}),
        }

    def __init__(self, *args, **kwargs):
        # Captura o 'user' passado pela view antes de qualquer outra coisa
        user = kwargs.pop('user', None)
        
        super().__init__(*args, **kwargs)

        # Se o usuário foi passado e é um superuser (administrador)...
        if user and user.is_superuser:
            # ...adiciona o campo 'vendedor' ao formulário.
            self.fields['vendedor'] = forms.ModelChoiceField(
                queryset=User.objects.all(), # Lista todos os usuários
                label="Vendedor Responsável",
                widget=forms.Select(attrs={'class': 'form-control'})
            )

        # Aplica a classe 'form-control' do Bootstrap a todos os campos
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})