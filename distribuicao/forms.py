from django import forms
from clientes.models import Cliente
import re
from django.contrib.auth.models import User
from .models import VendedorRodizio

class LeadEntradaForm(forms.ModelForm):
    # Campo de confirmação (inicia oculto ou desmarcado)
    redistribuir = forms.BooleanField(
        required=False, 
        initial=False,
        label="Sim, desejo redistribuir este lead.",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    lancamento_esporadico = forms.BooleanField(
        required=False,
        initial=False,
        label="Lançamento manual (esporádico, sem alterar fila)",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    vendedor_manual = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Vendedor para lançamento manual",
        widget=forms.Select(attrs={'class': 'form-select'})
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        vendedores_ids = (
            VendedorRodizio.objects.filter(ativo=True)
            .values_list('vendedor_id', flat=True)
        )
        self.fields['vendedor_manual'].queryset = User.objects.filter(id__in=vendedores_ids).order_by('first_name', 'username')
        self.fields['vendedor_manual'].empty_label = "Selecione o vendedor"
        self.fields['lancamento_esporadico'].help_text = "Usa o vendedor escolhido apenas neste lead e mantém a fila atual."
        self.fields['vendedor_manual'].help_text = "Obrigatório quando lançamento manual estiver marcado."

    def clean(self):
        cleaned_data = super().clean()
        whatsapp = cleaned_data.get('whatsapp')
        redistribuir = cleaned_data.get('redistribuir')
        lancamento_esporadico = cleaned_data.get('lancamento_esporadico')
        vendedor_manual = cleaned_data.get('vendedor_manual')

        if lancamento_esporadico and not vendedor_manual:
            self.add_error('vendedor_manual', "Selecione o vendedor para lançamento manual.")

        if vendedor_manual and not VendedorRodizio.objects.filter(vendedor=vendedor_manual, ativo=True).exists():
            self.add_error('vendedor_manual', "O vendedor selecionado não está ativo no rodízio.")

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
