from django.contrib.auth.models import User
from django import forms
from .models import Cliente, Historico, LeadAndamento


class ClienteForm(forms.ModelForm):
    data_proximo_contato = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )

    class Meta:
        model = Cliente
        fields = [
            'whatsapp', 'nome_cliente', 'email', 'tipo_veiculo',
            'marca_veiculo', 'modelo_veiculo', 'ano_veiculo', 'valor_estimado_veiculo',
            'fonte_cliente', 'quantidade_ligacoes', 'tipo_negociacao', 'tipo_contato',
            'status_negociacao', 'status_contato', 'etapa_funil', 'proximo_passo', 'prioridade', 'observacao', 'vendedor',
            'data_proximo_contato'
        ]
        widgets = {
            'observacao': forms.Textarea(attrs={'rows': 3}),
            'whatsapp': forms.TextInput(attrs={'placeholder': '(99) 9 9999-9999'}),
            'email': forms.EmailInput(attrs={'placeholder': 'email@cliente.com'}),
            'valor_estimado_veiculo': forms.TextInput(attrs={'placeholder': 'R$ 0,00'}),
            'marca_veiculo': forms.TextInput(attrs={'placeholder': 'Ex: Chevrolet'}),
            'modelo_veiculo': forms.TextInput(attrs={'placeholder': 'Ex: Onix 1.0'}),
            'ano_veiculo': forms.TextInput(attrs={'placeholder': 'Ex: 2022'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            if field_name != 'data_proximo_contato':
                field.widget.attrs.update({'class': 'form-control'})

        if user and not user.is_superuser:
            self.fields['vendedor'].disabled = True
            self.fields['vendedor'].required = False


class HistoricoForm(forms.ModelForm):
    class Meta:
        model = Historico
        fields = ['motivacao']
        widgets = {
            'motivacao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva a nova interacao...'}),
        }


class LeadAndamentoForm(forms.ModelForm):
    data_proxima_acao = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )

    class Meta:
        model = LeadAndamento
        fields = ['status_contato', 'etapa_funil', 'proximo_passo', 'data_proxima_acao', 'comentario']
        widgets = {
            'status_contato': forms.Select(attrs={'class': 'form-select'}),
            'etapa_funil': forms.Select(attrs={'class': 'form-select'}),
            'proximo_passo': forms.Select(attrs={'class': 'form-select'}),
            'comentario': forms.Textarea(
                attrs={
                    'rows': 4,
                    'class': 'form-control',
                    'placeholder': 'Ex.: Cliente pediu simulacao com entrada de R$ 20 mil e retorno ate amanha as 10h.'
                }
            ),
        }
