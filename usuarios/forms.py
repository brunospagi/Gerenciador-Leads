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

# --- NOVO FORMULÁRIO PARA A PÁGINA DE PERFIL ---
class ProfileAvatarForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar']
        widgets = {
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'})
        }


class UserCreationFormByAdmin(forms.ModelForm):
    # ... (código existente)
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)
    nivel_acesso = forms.ChoiceField(choices=Profile.NivelAcesso.choices, required=True)
    # --- ADICIONADO CAMPO AVATAR ---
    avatar = forms.ImageField(label="Avatar", required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        # --- ADICIONADO 'avatar' ---
        fields = ('username', 'email', 'first_name', 'last_name', 'nivel_acesso', 'avatar')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            user.profile.nivel_acesso = self.cleaned_data['nivel_acesso']
            # --- ADICIONADO LÓGICA DE SALVAR AVATAR ---
            user.profile.avatar = self.cleaned_data.get('avatar')
            user.profile.save()
        return user

class UserUpdateFormByAdmin(forms.ModelForm):
    # ... (código existente)
    nivel_acesso = forms.ChoiceField(choices=Profile.NivelAcesso.choices)
    # --- ADICIONADO CAMPO AVATAR (Clearable para permitir remoção) ---
    avatar = forms.ImageField(label="Avatar", required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        # --- ADICIONADO 'avatar' ---
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active', 'avatar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['nivel_acesso'].initial = self.instance.profile.nivel_acesso
            # --- ADICIONADO VALOR INICIAL DO AVATAR ---
            self.fields['avatar'].initial = self.instance.profile.avatar

    def save(self, commit=True):
        user = super().save(commit=commit)
        user.profile.nivel_acesso = self.cleaned_data['nivel_acesso']
        
        # --- LÓGICA DE ATUALIZAÇÃO DO AVATAR ---
        avatar_data = self.cleaned_data.get('avatar')
        if avatar_data is not None: # Campo estava presente no form
            if avatar_data == False: # Checkbox "clear" foi marcado
                user.profile.avatar = None
            elif avatar_data: # Um novo arquivo foi enviado
                user.profile.avatar = avatar_data
        # Se avatar_data for None, significa que o campo não foi alterado
        
        user.profile.save()
        return user