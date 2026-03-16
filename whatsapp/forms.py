from django import forms

from .models import WhatsAppInstance


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


class WhatsAppInstanceForm(forms.ModelForm):
    class Meta:
        model = WhatsAppInstance
        fields = ['nome', 'api_base_url', 'api_key', 'instance_name', 'webhook_secret', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Matriz'}),
            'api_base_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://evolution.seudominio.com'}),
            'api_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'API key global da Evolution'}),
            'instance_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'nome-da-instancia'}),
            'webhook_secret': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class WhatsAppConnectForm(forms.Form):
    numero = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Opcional: 5511999999999',
            }
        ),
    )
