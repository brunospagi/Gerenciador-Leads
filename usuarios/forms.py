from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.models import User
from .models import Profile

class CustomPasswordChangeForm(PasswordChangeForm):
    # ... (código existente sem alterações)
    old_password = forms.CharField(
        label="Senha Antiga",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Digite sua senha antiga'})
    )
    new_password1 = forms.CharField(
        label="Nova Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Digite sua nova senha'})
    )
    new_password2 = forms.CharField(
        label="Confirmação da Nova Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirme sua nova senha'})
    )

# >> NOVO FORMULÁRIO PARA ADMIN ALTERAR SENHA <<
class AdminSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="Nova Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Digite a nova senha'})
    )
    new_password2 = forms.CharField(
        label="Confirmação da Nova Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirme a nova senha'})
    )


class UserCreationFormByAdmin(forms.ModelForm):
    # ... (código existente sem alterações)
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)
    nivel_acesso = forms.ChoiceField(choices=Profile.NivelAcesso.choices, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'nivel_acesso')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            user.profile.nivel_acesso = self.cleaned_data['nivel_acesso']
            user.profile.save()
        return user

class UserUpdateFormByAdmin(forms.ModelForm):
    # ... (código existente sem alterações)
    nivel_acesso = forms.ChoiceField(choices=Profile.NivelAcesso.choices)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['nivel_acesso'].initial = self.instance.profile.nivel_acesso

    def save(self, commit=True):
        user = super().save(commit=commit)
        user.profile.nivel_acesso = self.cleaned_data['nivel_acesso']
        user.profile.save()
        return user