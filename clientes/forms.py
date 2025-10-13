from django import forms
from .models import Cliente, Historico
from django.contrib.auth.models import User

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'whatsapp', 'nome_cliente', 'modelo_veiculo', 'valor_estimado_veiculo',
            'fonte_cliente', 'quantidade_ligacoes', 'tipo_negociacao', 'tipo_contato',
            'status_negociacao', 'proximo_passo', 'prioridade', 'observacao', 'vendedor'
        ]
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
            'whatsapp': forms.TextInput(attrs={'placeholder': '(99) 9 9999-9999'}),
            'valor_estimado_veiculo': forms.TextInput(attrs={'placeholder': 'R$ 0,00'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Aplica a classe 'form-control' a todos os campos
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

        # Se o usuário NÃO for um administrador...
        if user and not user.is_superuser:
            # >> ESTA É A CORREÇÃO PRINCIPAL <<
            # Desabilitamos o campo 'vendedor'. Isso o torna visível, mas não editável.
            # O navegador enviará o valor do campo, evitando o erro de valor nulo.
            self.fields['vendedor'].disabled = True
            self.fields['vendedor'].widget.attrs['title'] = 'Você não tem permissão para alterar o vendedor.'
            self.fields['vendedor'].label = "Vendedor (não pode ser alterado)"

class HistoricoForm(forms.ModelForm):
    class Meta:
        model = Historico
        fields = ['motivacao']
        widgets = {
            'motivacao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva a nova interação...'}),
        }