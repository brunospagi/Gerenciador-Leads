from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, TemplateView, UpdateView

from clientes.models import Cliente, Historico
from .forms import LeadEntradaForm
from .logic import (
    definir_proximo_vendedor,
    enviar_webhook_n8n,
    vendedor_disponivel_no_rodizio,
)


class PainelDistribuicaoView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Cliente
    form_class = LeadEntradaForm
    template_name = 'distribuicao/painel_entrada.html'
    success_url = reverse_lazy('painel-distribuicao')

    def test_func(self):
        user_profile = getattr(self.request.user, 'profile', None)
        if self.request.user.is_superuser:
            return True
        if user_profile and user_profile.nivel_acesso in ['DISTRIBUIDOR', 'ADMIN', 'GERENTE']:
            return True
        if user_profile and user_profile.pode_distribuir_leads:
            return True
        return False

    def handle_no_permission(self):
        messages.error(self.request, 'Acesso negado. Voce nao tem permissao para distribuir leads.')
        return redirect('portal')

    def form_valid(self, form):
        is_redistribuicao = form.instance.pk is not None
        vendedor_antigo = form.instance.vendedor if is_redistribuicao else None

        lancamento_esporadico = bool(form.cleaned_data.get('lancamento_esporadico'))
        vendedor_manual = form.cleaned_data.get('vendedor_manual')
        if lancamento_esporadico and vendedor_manual:
            if not vendedor_disponivel_no_rodizio(vendedor_manual):
                form.add_error('vendedor_manual', 'Vendedor indisponivel no momento (regras de ponto/almoco).')
                messages.error(self.request, 'Vendedor manual bloqueado pelas regras de ponto/almoco.')
                return self.form_invalid(form)
            vendedor_selecionado = vendedor_manual
        else:
            vendedor_selecionado = definir_proximo_vendedor()

        if not vendedor_selecionado:
            form.add_error(
                None,
                'Nenhum vendedor elegivel no rodizio agora. Verifique entrada, saida/retorno de almoco e bloqueio apos 14:00.',
            )
            messages.error(
                self.request,
                'Nenhum vendedor elegivel no rodizio agora. Confira ponto de entrada e regras de almoco.',
            )
            return self.form_invalid(form)

        form.instance.vendedor = vendedor_selecionado
        form.instance.status_negociacao = Cliente.StatusNegociacao.NOVO
        form.instance.prioridade = Cliente.Prioridade.MORNO
        form.instance.tipo_contato = Cliente.TipoContato.MENSAGEM
        form.instance.proximo_passo = Cliente.ProximoPasso.MENSAGEM
        form.instance.data_proximo_contato = timezone.now()

        response = super().form_valid(form)

        if is_redistribuicao:
            Historico.objects.create(
                cliente=self.object,
                motivacao=(
                    f'Redistribuicao via Entrada (Duplicidade detectada). '
                    f'De: {vendedor_antigo.username} Para: {vendedor_selecionado.username}.'
                    + (' Lancamento manual esporadico (fila preservada).' if lancamento_esporadico else '')
                ),
            )
            msg = (
                f'Lead EXISTENTE atualizado e transferido de {vendedor_antigo.username} para: {vendedor_selecionado.username}'
                + (' (manual esporadico, fila preservada).' if lancamento_esporadico else '')
            )
            messages.warning(self.request, msg)
        else:
            msg = (
                f'Novo lead cadastrado e enviado para: {vendedor_selecionado.username}'
                + (' (manual esporadico, fila preservada).' if lancamento_esporadico else '')
            )
            messages.success(self.request, msg)

        enviar_webhook_n8n(self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ultimos_leads'] = Cliente.objects.order_by('-id')[:10]
        return context


class RelatorioDistribuicaoView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'distribuicao/relatorio_distribuicao.html'

    def get_template_names(self):
        if self.request.GET.get('print') == '1':
            return ['distribuicao/relatorio_distribuicao_print.html']
        return [self.template_name]

    def test_func(self):
        user_profile = getattr(self.request.user, 'profile', None)
        if self.request.user.is_superuser:
            return True
        if user_profile and user_profile.nivel_acesso in ['ADMIN', 'GERENTE', 'DISTRIBUIDOR']:
            return True
        if user_profile and user_profile.pode_distribuir_leads:
            return True
        return False

    def handle_no_permission(self):
        messages.error(self.request, 'Acesso restrito a perfis com permissao de distribuicao.')
        return redirect('portal')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agora = timezone.localtime(timezone.now())
        hoje = agora.date()

        data_diario_str = self.request.GET.get('data_diario')
        if data_diario_str:
            try:
                data_filtro = datetime.strptime(data_diario_str, '%Y-%m-%d').date()
            except ValueError:
                data_filtro = hoje
        else:
            data_filtro = hoje

        mes_mensal_str = self.request.GET.get('mes_mensal')
        if mes_mensal_str:
            try:
                dt_mes = datetime.strptime(mes_mensal_str, '%Y-%m')
                mes_ref, ano_ref = dt_mes.month, dt_mes.year
            except ValueError:
                mes_ref, ano_ref = hoje.month, hoje.year
                mes_mensal_str = hoje.strftime('%Y-%m')
        else:
            mes_ref, ano_ref = hoje.month, hoje.year
            mes_mensal_str = hoje.strftime('%Y-%m')

        active_tab = self.request.GET.get('tab', 'diario')
        if 'mes_mensal' in self.request.GET:
            active_tab = 'mensal'

        leads_dia = Cliente.objects.filter(data_primeiro_contato__date=data_filtro).select_related('vendedor').order_by('data_primeiro_contato')
        leads_manha = [l for l in leads_dia if timezone.localtime(l.data_primeiro_contato).hour < 12]
        leads_tarde = [l for l in leads_dia if timezone.localtime(l.data_primeiro_contato).hour >= 12]

        inicio_semana = hoje - timedelta(days=hoje.weekday())
        leads_semana = Cliente.objects.filter(data_primeiro_contato__date__gte=inicio_semana).select_related('vendedor').order_by('-data_primeiro_contato')

        leads_mes = Cliente.objects.filter(
            data_primeiro_contato__month=mes_ref,
            data_primeiro_contato__year=ano_ref,
        ).select_related('vendedor').order_by('-data_primeiro_contato')

        context.update(
            {
                'active_tab': active_tab,
                'data_hoje': data_filtro,
                'data_diario_val': data_filtro.strftime('%Y-%m-%d'),
                'leads_manha': leads_manha,
                'total_manha': len(leads_manha),
                'leads_tarde': leads_tarde,
                'total_tarde': len(leads_tarde),
                'total_hoje': len(leads_dia),
                'leads_semana': leads_semana,
                'total_semana': leads_semana.count(),
                'mes_atual_str': mes_mensal_str,
                'leads_mes': leads_mes,
                'total_mes': leads_mes.count(),
            }
        )
        return context


class RedistribuirLeadView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Cliente
    template_name = 'distribuicao/redistribuir_confirm.html'
    fields = []

    def test_func(self):
        user_profile = getattr(self.request.user, 'profile', None)
        if self.request.user.is_superuser:
            return True
        if user_profile and user_profile.nivel_acesso in ['ADMIN', 'GERENTE', 'DISTRIBUIDOR']:
            return True
        return False

    def handle_no_permission(self):
        messages.error(self.request, 'Voce nao tem permissao para redistribuir leads.')
        return redirect('portal')

    def form_valid(self, form):
        cliente = self.object
        vendedor_antigo = cliente.vendedor
        novo_vendedor = definir_proximo_vendedor()

        if not novo_vendedor:
            messages.error(self.request, 'Nao ha vendedores elegiveis no rodizio.')
            return redirect('painel-distribuicao')

        cliente.vendedor = novo_vendedor
        cliente.save()

        try:
            enviar_webhook_n8n(cliente)
        except Exception as e:
            print(f'Erro ao enviar webhook na redistribuicao: {e}')

        Historico.objects.create(
            cliente=cliente,
            motivacao=(
                f'Redistribuido manualmente (Rodizio). '
                f'De: {vendedor_antigo.username} Para: {novo_vendedor.username} por {self.request.user.username}.'
            ),
        )

        messages.success(self.request, f'Lead redistribuido para {novo_vendedor.username}!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('painel-distribuicao')
