from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from usuarios.views import AdminRequiredMixin

from .forms import ConfiguracaoIntegracoesForm, WebhookIntegracaoForm
from .models import ConfiguracaoIntegracoes, ModuloSistema, PermissaoModulo, WebhookIntegracao

ACOES_PERMISSAO = [
    ('pode_visualizar', 'Visualizar'),
    ('pode_criar', 'Criar'),
    ('pode_editar', 'Editar'),
    ('pode_excluir', 'Excluir'),
]


class ConfiguracoesHomeView(AdminRequiredMixin, TemplateView):
    template_name = 'configuracoes/configuracoes_home.html'


class WebhookIntegracaoListView(AdminRequiredMixin, ListView):
    model = WebhookIntegracao
    template_name = 'configuracoes/webhook_list.html'
    context_object_name = 'webhooks'


class WebhookIntegracaoCreateView(AdminRequiredMixin, CreateView):
    model = WebhookIntegracao
    form_class = WebhookIntegracaoForm
    template_name = 'configuracoes/webhook_form.html'
    success_url = reverse_lazy('webhook_list')

    def form_valid(self, form):
        form.instance.sistema = False
        form.instance.atualizado_por = self.request.user
        messages.success(self.request, "Webhook cadastrado com sucesso.")
        return super().form_valid(form)


class WebhookIntegracaoUpdateView(AdminRequiredMixin, UpdateView):
    model = WebhookIntegracao
    form_class = WebhookIntegracaoForm
    template_name = 'configuracoes/webhook_form.html'
    success_url = reverse_lazy('webhook_list')

    def form_valid(self, form):
        form.instance.atualizado_por = self.request.user
        messages.success(self.request, "Webhook atualizado com sucesso.")
        return super().form_valid(form)


class WebhookIntegracaoDeleteView(AdminRequiredMixin, DeleteView):
    model = WebhookIntegracao
    template_name = 'configuracoes/webhook_confirm_delete.html'
    success_url = reverse_lazy('webhook_list')

    def get_queryset(self):
        return WebhookIntegracao.objects.filter(sistema=False)


class ConfiguracaoIntegracoesUpdateView(AdminRequiredMixin, UpdateView):
    model = ConfiguracaoIntegracoes
    form_class = ConfiguracaoIntegracoesForm
    template_name = 'configuracoes/integracoes_form.html'
    success_url = reverse_lazy('configuracoes_home')

    def get_object(self, queryset=None):
        return ConfiguracaoIntegracoes.get_solo()

    def form_valid(self, form):
        form.instance.atualizado_por = self.request.user
        messages.success(self.request, "Integrações externas atualizadas com sucesso.")
        return super().form_valid(form)


class PermissaoModuloListView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'configuracoes/permissao_list.html'
    context_object_name = 'usuarios'

    def get_queryset(self):
        return User.objects.select_related('profile').order_by('username')


class PermissaoModuloMatrixView(AdminRequiredMixin, TemplateView):
    template_name = 'configuracoes/permissao_matrix.html'

    def _target_user(self):
        return get_object_or_404(User, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_user = self._target_user()
        permissoes = {
            p.modulo_id: p
            for p in PermissaoModulo.objects.filter(user=target_user)
        }
        linhas = []
        for modulo in ModuloSistema.objects.all():
            permissao = permissoes.get(modulo.id)
            linhas.append({
                'modulo': modulo,
                'campos': [
                    (campo, getattr(permissao, campo, False) if permissao else False)
                    for campo, _ in ACOES_PERMISSAO
                ],
            })
        context['target_user'] = target_user
        context['linhas'] = linhas
        context['acoes'] = ACOES_PERMISSAO
        return context

    def post(self, request, *args, **kwargs):
        target_user = self._target_user()
        for modulo in ModuloSistema.objects.all():
            valores = {
                campo: request.POST.get(f'modulo_{modulo.slug}_{campo}') == 'on'
                for campo, _ in ACOES_PERMISSAO
            }
            PermissaoModulo.objects.update_or_create(
                user=target_user, modulo=modulo, defaults=valores,
            )
        messages.success(request, f"Permissões atualizadas para {target_user.username}.")
        return redirect('user_module_permissions')
