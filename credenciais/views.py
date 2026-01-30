from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Credencial
from .forms import CredencialForm

# Mixin de Permissão: Apenas Admin ou Gerente pode editar/criar
class GestorPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        # Superusuário sempre pode
        if user.is_superuser:
            return True
        # Verifica perfil
        if hasattr(user, 'profile'):
            return user.profile.nivel_acesso in ['ADMIN', 'GERENTE']
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "Você não tem permissão para realizar esta ação.")
        return super().handle_no_permission()

# Listagem: Todos podem ver
class CredencialListView(LoginRequiredMixin, ListView):
    model = Credencial
    template_name = 'credenciais/lista.html'
    context_object_name = 'credenciais'

# Create: Apenas Gestores
class CredencialCreateView(LoginRequiredMixin, GestorPermissionMixin, CreateView):
    model = Credencial
    form_class = CredencialForm
    template_name = 'credenciais/form.html'
    success_url = reverse_lazy('credencial_list')

    def form_valid(self, form):
        form.instance.atualizado_por = self.request.user
        messages.success(self.request, "Acesso cadastrado com sucesso!")
        return super().form_valid(form)

# Update: Apenas Gestores
class CredencialUpdateView(LoginRequiredMixin, GestorPermissionMixin, UpdateView):
    model = Credencial
    form_class = CredencialForm
    template_name = 'credenciais/form.html'
    success_url = reverse_lazy('credencial_list')

    def form_valid(self, form):
        form.instance.atualizado_por = self.request.user
        messages.success(self.request, "Dados de acesso atualizados!")
        return super().form_valid(form)

# Delete: Apenas Gestores
class CredencialDeleteView(LoginRequiredMixin, GestorPermissionMixin, DeleteView):
    model = Credencial
    template_name = 'credenciais/delete_confirm.html'
    success_url = reverse_lazy('credencial_list')