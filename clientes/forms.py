from django import forms # type: ignore
from .models import Cliente, Historico
from django.contrib.auth.models import User # type: ignore

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        # Mantemos 'vendedor' na lista de campos para que o formulário
        # sempre o considere ao salvar.
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
        # Capturamos o usuário e a instância (o cliente que está sendo editado)
        user = kwargs.pop('user', None)
        instance = kwargs.get('instance', None) # Usamos .get() para evitar erros se não houver instância

        super().__init__(*args, **kwargs)

        # Adiciona a classe 'form-control' a todos os campos, exceto 'vendedor'
        for field_name, field in self.fields.items():
            if field_name != 'vendedor':
                field.widget.attrs.update({'class': 'form-control'})

        # Se o usuário for um administrador...
        if user and user.is_superuser:
            # ...o campo 'vendedor' é um menu de seleção visível e obrigatório.
            self.fields['vendedor'].widget = forms.Select(attrs={'class': 'form-control'})
            self.fields['vendedor'].queryset = User.objects.all()
            self.fields['vendedor'].label = "Vendedor Responsável"
            self.fields['vendedor'].required = True
        else:
            # Se for um usuário normal...
            if instance and instance.pk:
                # >> ESTA É A CORREÇÃO PRINCIPAL <<
                # Se o formulário está editando um cliente existente (`instance.pk` tem valor),
                # preenchemos o campo 'vendedor' com o vendedor atual do cliente.
                # Isso garante que o valor seja mantido ao salvar.
                self.fields['vendedor'].initial = instance.vendedor
            
            # O campo é tornado não-obrigatório e oculto.
            # Ao criar, ele estará vazio (e a view o preencherá).
            # Ao editar, ele terá o valor inicial definido acima.
            self.fields['vendedor'].required = False
            self.fields['vendedor'].widget = forms.HiddenInput()


class HistoricoForm(forms.ModelForm):
    class Meta:
        model = Historico
        fields = ['motivacao']
        widgets = {
            'motivacao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva a nova interação...'}),
        }