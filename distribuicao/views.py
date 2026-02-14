from django.views.generic import CreateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta
from clientes.models import Cliente
from .forms import LeadEntradaForm
from .logic import definir_proximo_vendedor, enviar_webhook_n8n

class PainelDistribuicaoView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Cliente
    form_class = LeadEntradaForm
    template_name = 'distribuicao/painel_entrada.html'
    success_url = reverse_lazy('painel-distribuicao')

    def test_func(self):
        """
        Verifica se o usuário tem permissão para acessar o painel.
        """
        user_profile = getattr(self.request.user, 'profile', None)
        
        # 1. Se for Superusuário, sempre pode
        if self.request.user.is_superuser:
            return True

        if user_profile:
            # 2. Se tiver um dos cargos de gestão/distribuição
            cargos_permitidos = ['DISTRIBUIDOR', 'ADMIN', 'GERENTE']
            if user_profile.nivel_acesso in cargos_permitidos:
                return True
            
            # 3. Se tiver a PERMISSÃO EXTRA ativada (Híbrido)
            if user_profile.pode_distribuir_leads:
                return True
            
        return False

    def handle_no_permission(self):
        messages.error(self.request, "Acesso negado. Você não tem permissão para distribuir leads.")
        return redirect('portal')

    def form_valid(self, form):
        # Lógica de distribuição (Round-Robin)
        vendedor_selecionado = definir_proximo_vendedor()
        
        if not vendedor_selecionado:
            form.add_error(None, "ERRO: Nenhum vendedor ativo no rodízio!")
            return self.form_invalid(form)

        # Preenche os dados automáticos
        form.instance.vendedor = vendedor_selecionado
        form.instance.status_negociacao = Cliente.StatusNegociacao.NOVO
        form.instance.prioridade = Cliente.Prioridade.MORNO
        form.instance.tipo_contato = Cliente.TipoContato.MENSAGEM
        form.instance.proximo_passo = Cliente.ProximoPasso.MENSAGEM
        
        response = super().form_valid(form)
        
        # Envia para n8n e mostra mensagem
        enviar_webhook_n8n(self.object)
        messages.success(self.request, f"Lead enviado para: {vendedor_selecionado.username}")
        
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ultimos_leads'] = Cliente.objects.order_by('-id')[:10]
        return context

class RelatorioDistribuicaoView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'distribuicao/relatorio_distribuicao.html'

    def test_func(self):
        user_profile = getattr(self.request.user, 'profile', None)
        if self.request.user.is_superuser:
            return True
        # Permite Apenas Gerentes e Admins (Distribuidor não vê relatório gerencial, ajuste se necessário)
        if user_profile and user_profile.nivel_acesso in ['ADMIN', 'GERENTE']:
            return True
        return False

    def handle_no_permission(self):
        messages.error(self.request, "Acesso restrito a Gerentes e Administradores.")
        return redirect('portal')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agora = timezone.localtime(timezone.now())
        hoje = agora.date()
        
        # --- FILTRO DIÁRIO ---
        leads_dia = Cliente.objects.filter(
            data_primeiro_contato__date=hoje
        ).select_related('vendedor').order_by('data_primeiro_contato')

        # Separação Manhã (< 12:00) / Tarde (>= 12:00)
        leads_manha = []
        leads_tarde = []
        for lead in leads_dia:
            # Converte para hora local antes de comparar
            hora_lead = timezone.localtime(lead.data_primeiro_contato).hour
            if hora_lead < 12:
                leads_manha.append(lead)
            else:
                leads_tarde.append(lead)

        # --- FILTRO SEMANAL (Início da semana atual - Segunda-feira) ---
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        leads_semana = Cliente.objects.filter(
            data_primeiro_contato__date__gte=inicio_semana
        ).select_related('vendedor').order_by('-data_primeiro_contato')

        # --- FILTRO MENSAL ---
        leads_mes = Cliente.objects.filter(
            data_primeiro_contato__month=hoje.month,
            data_primeiro_contato__year=hoje.year
        ).select_related('vendedor').order_by('-data_primeiro_contato')

        context.update({
            'data_hoje': hoje,
            'leads_manha': leads_manha,
            'total_manha': len(leads_manha),
            'leads_tarde': leads_tarde,
            'total_tarde': len(leads_tarde),
            'total_hoje': len(leads_dia),
            
            'leads_semana': leads_semana,
            'total_semana': leads_semana.count(),
            
            'leads_mes': leads_mes,
            'total_mes': leads_mes.count(),
        })
        return context