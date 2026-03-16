from django import forms


class WhatsAppSendMessageForm(forms.Form):
    mensagem = forms.CharField(
        label='Mensagem',
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Digite a mensagem para o cliente...',
            }
        ),
        max_length=5000,
    )


class WhatsAppStartConversationForm(forms.Form):
    numero = forms.CharField(
        label='Numero (DDD + telefone)',
        max_length=20,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 5511999999999',
            }
        ),
    )
    nome_contato = forms.CharField(
        label='Nome do contato',
        required=False,
        max_length=180,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Opcional',
            }
        ),
    )
