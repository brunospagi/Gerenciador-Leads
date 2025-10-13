from django import forms # type: ignore
from .models import Cliente, Historico
from django.contrib.auth.models import User # type: ignore

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        # Define explicitamente os campos do formulário para o usuário preencher
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

        # Se o usuário for um superuser (administrador)...
        if user and user.is_superuser:
            # ...adiciona o campo 'vendedor' ao formulário para que ele possa ser editado.
            self.fields['vendedor'] = forms.ModelChoiceField(
                queryset=User.objects.all(), # Lista todos os usuários
                label="Vendedor Responsável",
                required=True, # Garante que um vendedor seja selecionado pelo admin
                # Se houver uma instância (edição), define o vendedor inicial
                initial=self.instance.vendedor if self.instance else None,
                widget=forms.Select(attrs={'class': 'form-control'})
            )
            # Se for um formulário de edição, garante que o campo vendedor venha preenchido
            if self.instance and self.instance.pk:
                 self.fields['vendedor'].initial = self.instance.vendedor


        # Aplica a classe 'form-control' do Bootstrap a todos os campos
        for field_name, field in self.fields.items():
            # Evita adicionar a classe ao campo de vendedor se ele não existir
            if field_name != 'vendedor' or (user and user.is_superuser):
                 field.widget.attrs.update({'class': 'form-control'})

class HistoricoForm(forms.ModelForm):
    class Meta:
        model = Historico
        fields = ['motivacao']
        widgets = {
            'motivacao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva a nova interação...'}),
        }