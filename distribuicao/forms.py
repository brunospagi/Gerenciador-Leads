from django import forms
from clientes.models import Cliente
import re

class LeadEntradaForm(forms.ModelForm):
    # Campo de confirmação (inicia oculto ou desmarcado)
    redistribuir = forms.BooleanField(
        required=False, 
        initial=False,
        label="Sim, desejo redistribuir este lead.",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Cliente
        fields = [
            'nome_cliente', 
            'whatsapp', 
            'tipo_veiculo', 
            'marca_veiculo', 
            'modelo_veiculo',
            # Valor Estimado removido daqui
            'fonte_cliente', 
            'observacao'
        ]
        widgets = {
            'nome_cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome completo'}),
            'whatsapp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(XX) XXXXX-XXXX', 'data-mask': '(00) 00000-0000'}),
            'tipo_veiculo': forms.Select(attrs={'class': 'form-select'}),
            'marca_veiculo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Honda'}),
            'modelo_veiculo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Civic'}),
            'fonte_cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Instagram, Indicação'}),
            'observacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        whatsapp = cleaned_data.get('whatsapp')
        redistribuir = cleaned_data.get('redistribuir')

        if whatsapp:
            # Remove formatação para buscar no banco (apenas números)
            numeros = re.sub(r'\D', '', whatsapp)
            
            # Busca cliente existente (contendo o número)
            cliente_existente = Cliente.objects.filter(whatsapp__icontains=numeros).first()
            
            if cliente_existente:
                # Se encontrou e o usuário NÃO marcou para redistribuir -> Bloqueia e avisa
                if not redistribuir:
                    # Formata a data para exibir no erro
                    data_fmt = cliente_existente.data_primeiro_contato.strftime('%d/%m/%Y às %H:%M')
                    vendedor_nome = cliente_existente.vendedor.get_full_name() or cliente_existente.vendedor.username
                    
                    msg_erro = (
                        f"⚠️ LEAD JÁ CADASTRADO! "
                        f"Pertence a: {vendedor_nome}. "
                        f"Data de entrada: {data_fmt}. "
                        "Se deseja transferir para um novo vendedor, marque a caixa 'Redistribuir' que apareceu abaixo."
                    )
                    
                    self.add_error('whatsapp', msg_erro)
                
                else:
                    # Se encontrou e MARCOU redistribuir -> Prepara para atualizar
                    # Truque do Django: Substituímos a instância do form pela existente do banco
                    self.instance = cliente_existente

        return cleaned_data