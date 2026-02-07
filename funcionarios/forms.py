from django import forms
from django.contrib.auth.models import User
from .models import Funcionario

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}), 
        label="Senha Inicial",
        help_text="Defina uma senha provisória para o colaborador."
    )
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}), 
        label="Nome"
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}), 
        label="Sobrenome"
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'}), 
        label="E-mail"
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}), 
        label="Usuário (Login)"
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'password']

class FuncionarioForm(forms.ModelForm):
    class Meta:
        model = Funcionario
        exclude = ['user'] # O usuário é vinculado automaticamente na view
        widgets = {
            'cpf': forms.TextInput(attrs={'class': 'form-control cpf-mask', 'placeholder': '000.000.000-00'}),
            'rg': forms.TextInput(attrs={'class': 'form-control'}),
            'data_nascimento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 00000-0000'}),
            
            'endereco': forms.TextInput(attrs={'class': 'form-control'}),
            'cep': forms.TextInput(attrs={'class': 'form-control cep-mask', 'placeholder': '00000-000'}),
            
            'cargo': forms.TextInput(attrs={'class': 'form-control'}),
            'data_admissao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'salario_base': forms.TextInput(attrs={'class': 'form-control money-mask', 'placeholder': 'R$ 0,00'}),
            
            'banco': forms.TextInput(attrs={'class': 'form-control'}),
            'agencia': forms.TextInput(attrs={'class': 'form-control'}),
            'conta': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_conta': forms.Select(attrs={'class': 'form-select'}),
            'chave_pix': forms.TextInput(attrs={'class': 'form-control'}),
            
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'checked': True}),
        }