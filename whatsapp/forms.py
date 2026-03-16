from django import forms
import mimetypes

from .models import WhatsAppInstance


MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_MIME_PREFIXES = ('image/', 'video/', 'audio/')
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
    'application/zip',
    'application/x-rar-compressed',
    'application/vnd.rar',
}


class WhatsAppSendMessageForm(forms.Form):
    mensagem = forms.CharField(
        label='Mensagem',
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Digite a mensagem (ou legenda da midia)...',
            }
        ),
        max_length=5000,
    )
    arquivo = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                'class': 'form-control',
                'accept': 'image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.txt,.zip,.rar',
            }
        ),
        label='Arquivo/midia',
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get('arquivo')
        if not arquivo:
            return arquivo

        if arquivo.size > MAX_UPLOAD_SIZE:
            raise forms.ValidationError('Arquivo excede 20MB. Envie um arquivo menor.')

        content_type = (getattr(arquivo, 'content_type', '') or '').lower()
        if not content_type:
            guessed, _ = mimetypes.guess_type(arquivo.name or '')
            content_type = (guessed or '').lower()

        is_allowed = any(content_type.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES)
        if not is_allowed and content_type not in ALLOWED_MIME_TYPES:
            raise forms.ValidationError('Tipo de arquivo nao permitido para envio no WhatsApp.')

        return arquivo


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
