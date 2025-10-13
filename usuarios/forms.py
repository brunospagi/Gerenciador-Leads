from django import forms
from django.contrib.auth.forms import PasswordChangeForm
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

# >> NOVO FORMULÁRIO PARA CRIAÇÃO DE USUÁRIOS PELO ADMIN <<
class UserCreationFormByAdmin(forms.ModelForm):
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
            # Salva o perfil com o nível de acesso
            user.profile.nivel_acesso = self.cleaned_data['nivel_acesso']
            user.profile.save()
        return user

# >> NOVO FORMULÁRIO PARA EDIÇÃO DE USUÁRIOS PELO ADMIN <<
class UserUpdateFormByAdmin(forms.ModelForm):
    nivel_acesso = forms.ChoiceField(choices=Profile.NivelAcesso.choices)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Preenche o campo de nível de acesso com o valor atual do perfil
        if self.instance.pk:
            self.fields['nivel_acesso'].initial = self.instance.profile.nivel_acesso

    def save(self, commit=True):
        user = super().save(commit=commit)
        # Salva o perfil com o nível de acesso atualizado
        user.profile.nivel_acesso = self.cleaned_data['nivel_acesso']
        user.profile.save()
        return user