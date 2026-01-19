# distribuicao/forms.py
import re
from django import forms
from clientes.models import Cliente

class LeadEntradaForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome_cliente', 'modelo_veiculo', 'whatsapp', 'fonte_cliente', 'observacao']
        widgets = {
            'nome_cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Cliente'}),
            'modelo_veiculo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Veículo de Interesse'}),
            'whatsapp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(XX) XXXXX-XXXX'}),
            'fonte_cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Instagram, Indicação'}),
            'observacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_whatsapp(self):
        """
        Remove formatação (pontos, traços, parênteses) e verifica duplicidade apenas com números.
        """
        whatsapp = self.cleaned_data.get('whatsapp')
        
        if whatsapp:
            # Remove tudo que NÃO for dígito (0-9)
            whatsapp_limpo = re.sub(r'\D', '', whatsapp)
            
            # Validação básica de tamanho (opcional, ajustável conforme necessidade)
            if len(whatsapp_limpo) < 10:
                raise forms.ValidationError("O número de telefone parece inválido (muito curto).")

            # Verifica duplicidade usando o número LIMPO
            qs = Cliente.objects.filter(whatsapp=whatsapp_limpo)
            
            # Se for edição, exclui o próprio ID da checagem
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(f"Duplicidade: Já existe um cliente com o número {whatsapp_limpo}.")
            
            # Retorna o número limpo para ser salvo no banco
            return whatsapp_limpo
            
        return whatsapp