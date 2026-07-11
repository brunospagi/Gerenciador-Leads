from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from configuracoes.access import ModuleActionRequiredMixin
from .models import Credencial
from .forms import CredencialForm

# Listagem: qualquer um com acesso ao módulo
class CredencialListView(ModuleActionRequiredMixin, ListView):
    module_key = 'credenciais'
    module_action = 'visualizar'
    model = Credencial
    template_name = 'credenciais/lista.html'
    context_object_name = 'credenciais'

# Create: apenas quem tem a ação "criar" liberada
class CredencialCreateView(ModuleActionRequiredMixin, CreateView):
    module_key = 'credenciais'
    module_action = 'criar'
    model = Credencial
    form_class = CredencialForm
    template_name = 'credenciais/form.html'
    success_url = reverse_lazy('credencial_list')

    def form_valid(self, form):
        form.instance.atualizado_por = self.request.user
        messages.success(self.request, "Acesso cadastrado com sucesso!")
        return super().form_valid(form)

# Update: apenas quem tem a ação "editar" liberada
class CredencialUpdateView(ModuleActionRequiredMixin, UpdateView):
    module_key = 'credenciais'
    module_action = 'editar'
    model = Credencial
    form_class = CredencialForm
    template_name = 'credenciais/form.html'
    success_url = reverse_lazy('credencial_list')

    def form_valid(self, form):
        form.instance.atualizado_por = self.request.user
        messages.success(self.request, "Dados de acesso atualizados!")
        return super().form_valid(form)

# Delete: apenas quem tem a ação "excluir" liberada
class CredencialDeleteView(ModuleActionRequiredMixin, DeleteView):
    module_key = 'credenciais'
    module_action = 'excluir'
    model = Credencial
    template_name = 'credenciais/delete_confirm.html'
    success_url = reverse_lazy('credencial_list')
