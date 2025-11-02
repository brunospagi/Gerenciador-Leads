from django import forms
from .models import Procuracao, Outorgado # Adicionado Outorgado

class OutorgadoForm(forms.ModelForm):
    """
    Formulário para criar e editar Outorgados.
    """
    class Meta:
        model = Outorgado
        fields = ['nome', 'cpf']
        widgets = {
            'nome': forms.TextInput(attrs={'placeholder': 'Nome completo'}),
            'cpf': forms.TextInput(attrs={'placeholder': '000.000.000-00'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})


class ProcuracaoForm(forms.ModelForm):
    class Meta:
        model = Procuracao
        fields = [
            'outorgante_nome', 'tipo_documento', 'outorgante_documento',
            'veiculo_marca_modelo', 'veiculo_ano_fab', 'veiculo_ano_mod',
            'veiculo_placa', 'veiculo_cor', 'veiculo_renavam'
        ]
        widgets = {
            'tipo_documento': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'outorgante_nome': forms.TextInput(attrs={'placeholder': 'Nome completo como no documento'}),
            'outorgante_documento': forms.TextInput(attrs={'placeholder': 'Selecione o tipo de documento'}),
            'veiculo_marca_modelo': forms.TextInput(attrs={'placeholder': 'Ex: HONDA/XRE 190 SE'}),
            'veiculo_ano_fab': forms.TextInput(attrs={'placeholder': '2022'}),
            'veiculo_ano_mod': forms.TextInput(attrs={'placeholder': '2023'}),
            'veiculo_placa': forms.TextInput(attrs={'placeholder': 'AAA1B23'}),
            'veiculo_cor': forms.TextInput(attrs={'placeholder': 'CINZA'}),
            'veiculo_renavam': forms.TextInput(attrs={'placeholder': '00000000000'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplica a classe 'form-control' a todos os campos, exceto o RadioSelect
        for field_name, field in self.fields.items():
            if field_name != 'tipo_documento':
                field.widget.attrs.update({'class': 'form-control'})

class CRLVUploadForm(forms.Form):
    """
    Formulário para o upload do PDF do CRLV-e.
    """
    crlv_pdf = forms.FileField(
        label="Carregar CRLV-e (PDF)",
        required=True,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf'})
    )