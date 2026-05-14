from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth.models import User

from .models import Funcionario


class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Senha Inicial',
        help_text='Defina uma senha provisória para o colaborador.',
    )
    first_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}), label='Nome')
    last_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}), label='Sobrenome')
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}), label='E-mail')
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}), label='Usuário (Login)')

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'password']


class UserUpdateForm(forms.ModelForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}), label='Nome')
    last_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}), label='Sobrenome')
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}), label='E-mail')
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}), label='Usuário (Login)')

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']


class FuncionarioForm(forms.ModelForm):
    salario_base = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': 'R$ 0,00'}),
        label='Salário Base (R$)',
    )

    class Meta:
        model = Funcionario
        exclude = ['user']
        widgets = {
            'cpf': forms.TextInput(attrs={'class': 'form-control cpf-mask', 'placeholder': '000.000.000-00'}),
            'rg': forms.TextInput(attrs={'class': 'form-control'}),
            'data_nascimento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 00000-0000'}),
            'endereco': forms.TextInput(attrs={'class': 'form-control'}),
            'cep': forms.TextInput(attrs={'class': 'form-control cep-mask', 'placeholder': '00000-000'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control'}),
            'data_admissao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_ultimo_dia_trabalhado': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'banco': forms.TextInput(attrs={'class': 'form-control'}),
            'agencia': forms.TextInput(attrs={'class': 'form-control'}),
            'conta': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_conta': forms.Select(attrs={'class': 'form-select'}),
            'chave_pix': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'checked': True}),
            'opta_vt': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'valor_diario_vt': forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': '0,00'}),
            'foto_biometria': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        ativo = cleaned_data.get('ativo')
        ultimo_dia = cleaned_data.get('data_ultimo_dia_trabalhado')

        if ativo is False and not ultimo_dia:
            self.add_error('data_ultimo_dia_trabalhado', 'Informe o último dia trabalhado para colaborador inativo.')

        if ativo is True:
            cleaned_data['data_ultimo_dia_trabalhado'] = None

        return cleaned_data

    def clean_salario_base(self):
        valor = self.cleaned_data.get('salario_base')
        if isinstance(valor, Decimal):
            return valor
        if valor in (None, ''):
            raise forms.ValidationError('Informe um salário válido.')

        valor_str = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        try:
            return Decimal(valor_str)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Informe um salário válido.')

    def clean_valor_diario_vt(self):
        valor = self.cleaned_data.get('valor_diario_vt')
        if isinstance(valor, Decimal):
            return valor
        if valor in (None, ''):
            return Decimal('0.00')
        valor_str = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        try:
            return Decimal(valor_str)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Informe um valor diário de VT válido.')
