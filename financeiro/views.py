from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .models import TransacaoFinanceira, gerar_relatorio_DRE_mensal
from .forms import TransacaoFinanceiraForm
from usuarios.permissions import has_module_access

class AcessoFinanceiroMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        if self.request.user.is_superuser:
            return True
        profile = getattr(self.request.user, 'profile', None)
        if not profile:
            return False
        return (
            profile.nivel_acesso == 'ADMIN'
            or profile.pode_acessar_financeiro
            or has_module_access(self.request.user, 'financeiro')
        )

class AcessoAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        if self.request.user.is_superuser:
            return True
        profile = getattr(self.request.user, 'profile', None)
        if not profile:
            return False
        return profile.nivel_acesso == 'ADMIN'

class TransacaoListView(AcessoFinanceiroMixin, ListView):
    model = TransacaoFinanceira
    template_name = 'financeiro/lista_transacoes.html'
    context_object_name = 'transacoes'
    
    def get_queryset(self):
        user = self.request.user

        # Mantém recorrentes em dia ao virar o mês.
        if user.profile.nivel_acesso == 'ADMIN':
            TransacaoFinanceira.gerar_recorrentes_ate_mes_atual(owner=None)
            return TransacaoFinanceira.objects.all().order_by('-data_vencimento')

        TransacaoFinanceira.gerar_recorrentes_ate_mes_atual(owner=user)
        # Se for o usuário do Financeiro, vê APENAS as que ele mesmo criou
        return TransacaoFinanceira.objects.filter(criado_por=user).order_by('-data_vencimento')

class TransacaoCreateView(AcessoFinanceiroMixin, CreateView):
    model = TransacaoFinanceira
    form_class = TransacaoFinanceiraForm
    template_name = 'financeiro/form_transacao.html'
    success_url = reverse_lazy('financeiro:lista_transacoes')

    # SALVA O USUÁRIO LOGADO AUTOMATICAMENTE COMO CRIADOR DA CONTA
    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        return super().form_valid(form)

class TransacaoUpdateView(AcessoAdminMixin, UpdateView):
    model = TransacaoFinanceira
    form_class = TransacaoFinanceiraForm
    template_name = 'financeiro/form_transacao.html'
    success_url = reverse_lazy('financeiro:lista_transacoes')

class TransacaoDeleteView(AcessoAdminMixin, DeleteView):
    model = TransacaoFinanceira
    template_name = 'financeiro/confirmar_delete.html'
    success_url = reverse_lazy('financeiro:lista_transacoes')

class RelatorioDREView(AcessoAdminMixin, TemplateView):
    template_name = 'financeiro/relatorio_dre.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoje = timezone.now()
        mes = int(self.request.GET.get('mes', hoje.month))
        ano = int(self.request.GET.get('ano', hoje.year))
        
        context['relatorio'] = gerar_relatorio_DRE_mensal(mes, ano)
        context['mes_atual'] = mes
        context['ano_atual'] = ano
        
        if 'print' in self.request.GET:
            self.template_name = 'financeiro/relatorio_dre_print.html'
            
        return context
