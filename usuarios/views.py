from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import CustomPasswordChangeForm, UserCreationFormByAdmin, UserUpdateFormByAdmin, AdminSetPasswordForm
from django.contrib.auth.models import User
from .models import Profile

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    # ... (código existente sem alterações)
    def test_func(self):
        return hasattr(self.request.user, 'profile') and self.request.user.profile.nivel_acesso == Profile.NivelAcesso.ADMIN

# ... (outras views existentes)
@login_required
def profile_view(request):
    return render(request, 'usuarios/profile.html')

class CustomPasswordChangeView(PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'usuarios/password_change.html'
    success_url = reverse_lazy('profile')

    def form_valid(self, form):
        messages.success(self.request, 'Sua senha foi alterada com sucesso!')
        return super().form_valid(form)

class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'usuarios/user_list.html'
    context_object_name = 'usuarios'

class UserCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreationFormByAdmin
    template_name = 'usuarios/user_form.html'
    success_url = reverse_lazy('user_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Criar Novo Usuário"
        return context

class UserUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateFormByAdmin
    template_name = 'usuarios/user_form.html'
    success_url = reverse_lazy('user_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Editar Usuário"
        return context

class UserDeleteView(AdminRequiredMixin, DeleteView):
    model = User
    template_name = 'usuarios/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')


# >> NOVA VIEW PARA ADMIN ALTERAR SENHA DE OUTRO USUÁRIO <<
class UserPasswordChangeView(AdminRequiredMixin, FormView):
    form_class = AdminSetPasswordForm
    template_name = 'usuarios/user_password_change.html'
    success_url = reverse_lazy('user_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Passa o usuário alvo (obtido da URL) para o formulário
        kwargs['user'] = User.objects.get(pk=self.kwargs['pk'])
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, f"A senha para o usuário '{form.user.username}' foi alterada com sucesso.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Passa o usuário alvo para o template, para exibir seu nome
        context['target_user'] = User.objects.get(pk=self.kwargs['pk'])
        return context