from django import forms # type: ignore
from .models import Cliente, Historico
from django.contrib.auth.models import User # type: ignore

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = '__all__'
        # O campo 'vendedor' foi removido desta lista para que possamos adicioná-lo dinamicamente
        exclude = ('data_primeiro_contato', 'data_ultimo_contato', 'data_proximo_contato')
        
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

class HistoricoForm(forms.ModelForm):
    class Meta:
        model = Historico
        fields = ['motivacao']
        widgets = {
            'motivacao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva a nova interação...'}),
        }