from django import forms # type: ignore
from .models import Cliente, Historico
from django.contrib.auth.models import User # type: ignore

# --- Formulário para Criar e Editar Clientes ---
class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        # A lista 'fields' define quais campos do modelo 'Cliente' estarão no formulário.
        # É importante incluir o campo 'vendedor' aqui para que o Django saiba que
        # ele faz parte do formulário e o salve corretamente.
        fields = [
            'whatsapp', 'nome_cliente', 'modelo_veiculo', 'valor_estimado_veiculo',
            'fonte_cliente', 'quantidade_ligacoes', 'tipo_negociacao', 'tipo_contato',
            'status_negociacao', 'proximo_passo', 'prioridade', 'observacao', 'vendedor'
        ]
        
        # 'widgets' permitem customizar a aparência dos campos no HTML.
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}), # Aumenta a altura do campo de observação
            'whatsapp': forms.TextInput(attrs={'placeholder': '(99) 9 9999-9999'}),
            'valor_estimado_veiculo': forms.TextInput(attrs={'placeholder': 'R$ 0,00'}),
        }

    # O método __init__ é executado toda vez que o formulário é criado.
    # Usamos ele para fazer modificações dinâmicas nos campos.
    def __init__(self, *args, **kwargs):
        # Retiramos o 'user' dos argumentos passados pela view.
        # Isso é crucial para sabermos que tipo de usuário está acessando o formulário.
        user = kwargs.pop('user', None)
        
        # Chama o __init__ da classe pai para que o formulário seja construído normalmente.
        super().__init__(*args, **kwargs)

        # Adiciona a classe 'form-control' (do Bootstrap) a todos os campos,
        # exceto o de 'vendedor', que trataremos de forma especial.
        for field_name, field in self.fields.items():
            if field_name != 'vendedor':
                field.widget.attrs.update({'class': 'form-control'})

        # --- Lógica de Permissão para o Campo 'vendedor' ---
        # Verificamos se o usuário passado pela view é um superusuário (admin).
        if user and user.is_superuser:
            # Se for admin, o campo 'vendedor' será um menu de seleção.
            self.fields['vendedor'].widget = forms.Select(attrs={'class': 'form-control'})
            # A lista de opções incluirá todos os usuários cadastrados no sistema.
            self.fields['vendedor'].queryset = User.objects.all()
            # Definimos um nome amigável para o campo no formulário.
            self.fields['vendedor'].label = "Vendedor Responsável"
            # O campo se torna obrigatório para o admin.
            self.fields['vendedor'].required = True
        else:
            # Se não for admin (um vendedor comum), não queremos que ele escolha o vendedor.
            # O campo se torna não-obrigatório no formulário (a view vai preenchê-lo).
            self.fields['vendedor'].required = False
            # Ocultamos o campo do formulário. Ele ainda existe, mas fica invisível.
            self.fields['vendedor'].widget = forms.HiddenInput()

# --- Formulário para Adicionar Histórico de Interações ---
class HistoricoForm(forms.ModelForm):
    class Meta:
        model = Historico
        # Apenas o campo 'motivacao' é necessário, pois o resto é preenchido automaticamente.
        fields = ['motivacao']
        widgets = {
            'motivacao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva a nova interação...'}),
        }