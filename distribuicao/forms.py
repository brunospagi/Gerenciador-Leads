# distribuicao/forms.py
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
        Valida se o WhatsApp já existe no banco de dados para evitar duplicidade.
        """
        whatsapp = self.cleaned_data.get('whatsapp')
        
        # Remove espaços em branco antes e depois, se houver
        if whatsapp:
            whatsapp = whatsapp.strip()

        # Verifica se já existe algum cliente com esse número
        # Exclui a própria instância caso seja uma edição (embora este form seja usado para criação)
        qs = Cliente.objects.filter(whatsapp=whatsapp)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(f"Já existe um cliente cadastrado com este WhatsApp ({whatsapp}).")
            
        return whatsapp