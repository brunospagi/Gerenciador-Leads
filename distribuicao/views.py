from django.views.generic import CreateView, TemplateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta, datetime
from clientes.models import Cliente, Historico
from .forms import LeadEntradaForm
from .logic import definir_proximo_vendedor, enviar_webhook_n8n

class PainelDistribuicaoView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Cliente
    form_class = LeadEntradaForm
    template_name = 'distribuicao/painel_entrada.html'
    success_url = reverse_lazy('painel-distribuicao')

    def test_func(self):
        user_profile = getattr(self.request.user, 'profile', None)
        if self.request.user.is_superuser: return True
        if user_profile and user_profile.nivel_acesso in ['DISTRIBUIDOR', 'ADMIN', 'GERENTE']: return True
        if user_profile and user_profile.pode_distribuir_leads: return True
        return False

    def handle_no_permission(self):
        messages.error(self.request, "Acesso negado. Você não tem permissão para distribuir leads.")
        return redirect('portal')

    def form_valid(self, form):
        # Verifica se estamos redistribuindo um existente (o ID já existirá na instância se foi capturado no form.clean)
        is_redistribuicao = form.instance.pk is not None
        vendedor_antigo = form.instance.vendedor if is_redistribuicao else None

        # 1. Define o novo vendedor (Rodízio)
        vendedor_selecionado = definir_proximo_vendedor()
        
        if not vendedor_selecionado:
            form.add_error(None, "ERRO: Nenhum vendedor ativo no rodízio!")
            return self.form_invalid(form)

        # 2. Atualiza dados obrigatórios da distribuição
        form.instance.vendedor = vendedor_selecionado
        
        # Resetamos o status para NOVO para o novo vendedor trabalhar
        form.instance.status_negociacao = Cliente.StatusNegociacao.NOVO
        form.instance.prioridade = Cliente.Prioridade.MORNO
        form.instance.tipo_contato = Cliente.TipoContato.MENSAGEM
        form.instance.proximo_passo = Cliente.ProximoPasso.MENSAGEM
        
        # Se for redistribuição, atualiza a data de próximo contato para agora (para aparecer no topo da lista do vendedor)
        form.instance.data_proximo_contato = timezone.now()

        response = super().form_valid(form)
        
        # 3. Ações pós-salvamento e Feedback
        if is_redistribuicao:
            # Registra no histórico que foi redistribuído na entrada
            Historico.objects.create(
                cliente=self.object,
                motivacao=f"Redistribuição via Entrada (Duplicidade detectada). De: {vendedor_antigo.username} Para: {vendedor_selecionado.username}."
            )
            msg = f"Lead EXISTENTE atualizado e transferido de {vendedor_antigo.username} para: {vendedor_selecionado.username}"
            messages.warning(self.request, msg)
        else:
            msg = f"Novo lead cadastrado e enviado para: {vendedor_selecionado.username}"
            messages.success(self.request, msg)

        # Envia webhook
        enviar_webhook_n8n(self.object)
        
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Lista os 10 últimos para conferência rápida
        context['ultimos_leads'] = Cliente.objects.order_by('-id')[:10]
        return context


class RelatorioDistribuicaoView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'distribuicao/relatorio_distribuicao.html'

    def test_func(self):
        user_profile = getattr(self.request.user, 'profile', None)
        if self.request.user.is_superuser: return True
        if user_profile and user_profile.nivel_acesso in ['ADMIN', 'GERENTE']: return True
        return False

    def handle_no_permission(self):
        messages.error(self.request, "Acesso restrito a Gerentes e Administradores.")
        return redirect('portal')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agora = timezone.localtime(timezone.now())
        hoje = agora.date()
        
        # --- Lógica de Filtros (Dia e Mês) ---
        # Filtro Diário
        data_diario_str = self.request.GET.get('data_diario')
        data_filtro = datetime.strptime(data_diario_str, '%Y-%m-%d').date() if data_diario_str else hoje

        # Filtro Mensal
        mes_mensal_str = self.request.GET.get('mes_mensal')
        if mes_mensal_str:
            dt_mes = datetime.strptime(mes_mensal_str, '%Y-%m')
            mes_ref, ano_ref = dt_mes.month, dt_mes.year
        else:
            mes_ref, ano_ref = hoje.month, hoje.year
            mes_mensal_str = hoje.strftime('%Y-%m')

        # Aba Ativa
        active_tab = self.request.GET.get('tab', 'diario')
        if 'mes_mensal' in self.request.GET: active_tab = 'mensal'

        # Consultas
        leads_dia = Cliente.objects.filter(data_primeiro_contato__date=data_filtro).select_related('vendedor').order_by('data_primeiro_contato')
        
        leads_manha = [l for l in leads_dia if timezone.localtime(l.data_primeiro_contato).hour < 12]
        leads_tarde = [l for l in leads_dia if timezone.localtime(l.data_primeiro_contato).hour >= 12]

        inicio_semana = hoje - timedelta(days=hoje.weekday())
        leads_semana = Cliente.objects.filter(data_primeiro_contato__date__gte=inicio_semana).select_related('vendedor').order_by('-data_primeiro_contato')

        leads_mes = Cliente.objects.filter(data_primeiro_contato__month=mes_ref, data_primeiro_contato__year=ano_ref).select_related('vendedor').order_by('-data_primeiro_contato')

        context.update({
            'active_tab': active_tab,
            'data_hoje': data_filtro,
            'data_diario_val': data_filtro.strftime('%Y-%m-%d'),
            'leads_manha': leads_manha, 'total_manha': len(leads_manha),
            'leads_tarde': leads_tarde, 'total_tarde': len(leads_tarde),
            'total_hoje': len(leads_dia),
            'leads_semana': leads_semana, 'total_semana': leads_semana.count(),
            'mes_atual_str': mes_mensal_str,
            'leads_mes': leads_mes, 'total_mes': leads_mes.count(),
        })
        return context


class RedistribuirLeadView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Cliente
    template_name = 'distribuicao/redistribuir_confirm.html'
    fields = [] 

    def test_func(self):
        user_profile = getattr(self.request.user, 'profile', None)
        if self.request.user.is_superuser: return True
        if user_profile and user_profile.nivel_acesso in ['ADMIN', 'GERENTE', 'DISTRIBUIDOR']: return True
        return False

    def handle_no_permission(self):
        messages.error(self.request, "Você não tem permissão para redistribuir leads.")
        return redirect('portal')

    def form_valid(self, form):
        cliente = self.object
        vendedor_antigo = cliente.vendedor
        novo_vendedor = definir_proximo_vendedor()

        if not novo_vendedor:
            messages.error(self.request, "Não há vendedores ativos no rodízio.")
            return redirect('painel-distribuicao')

        cliente.vendedor = novo_vendedor
        cliente.save()

        Historico.objects.create(
            cliente=cliente,
            motivacao=f"Redistribuído manualmente (Rodízio). De: {vendedor_antigo.username} Para: {novo_vendedor.username} por {self.request.user.username}."
        )

        messages.success(self.request, f"Lead redistribuído para {novo_vendedor.username}!")
        return super().form_valid(form)

    def get_success_url(self):
        # Retorna para o painel de distribuição após redistribuir pela lista
        return reverse_lazy('painel-distribuicao')