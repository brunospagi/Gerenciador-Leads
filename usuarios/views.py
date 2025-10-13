from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import CustomPasswordChangeForm, UserCreationFormByAdmin, UserUpdateFormByAdmin
from django.contrib.auth.models import User

# Mixin para garantir que apenas administradores acessem a view
class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.profile.nivel_acesso == 'ADMIN'

@login_required
def profile_view(request):
    # ... (código existente sem alterações)
    return render(request, 'usuarios/profile.html')

class CustomPasswordChangeView(PasswordChangeView):
    # ... (código existente sem alterações)
    form_class = CustomPasswordChangeForm
    template_name = 'usuarios/password_change.html'
    success_url = reverse_lazy('profile')

    def form_valid(self, form):
        messages.success(self.request, 'Sua senha foi alterada com sucesso!')
        return super().form_valid(form)

# >> NOVAS VIEWS PARA GERENCIAMENTO DE USUÁRIOS <<
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