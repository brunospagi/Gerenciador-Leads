from django.views.generic import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
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
        Define QUEM pode acessar esta tela.
        Lógica Acumulativa: Admin, Gerente e Distribuidor podem acessar.
        """
        user_profile = getattr(self.request.user, 'profile', None)
        
        # Lista de perfis autorizados
        cargos_permitidos = ['DISTRIBUIDOR', 'ADMIN', 'GERENTE']
        
        if user_profile and user_profile.nivel_acesso in cargos_permitidos:
            return True
        
        # Também permite se for superusuário do Django
        if self.request.user.is_superuser:
            return True
            
        return False

    def handle_no_permission(self):
        # Redireciona para o portal em vez de mostrar erro 403
        messages.error(self.request, "Você não tem permissão para acessar a Distribuição de Leads.")
        return redirect('portal')

    def form_valid(self, form):
        # 1. Busca quem é o próximo da vez (Round-Robin)
        vendedor_selecionado = definir_proximo_vendedor()
        
        if not vendedor_selecionado:
            form.add_error(None, "ERRO CRÍTICO: Nenhum vendedor ativo no rodízio!")
            return self.form_invalid(form)

        # 2. Preenche os dados automáticos
        form.instance.vendedor = vendedor_selecionado
        form.instance.status_negociacao = Cliente.StatusNegociacao.NOVO
        form.instance.prioridade = Cliente.Prioridade.MORNO
        form.instance.tipo_contato = Cliente.TipoContato.MENSAGEM
        form.instance.proximo_passo = Cliente.ProximoPasso.MENSAGEM
        
        # 3. Salva
        response = super().form_valid(form)
        
        # 4. Webhook
        enviar_webhook_n8n(self.object)
        
        messages.success(self.request, f"Lead enviado para: {vendedor_selecionado.username}")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ultimos_leads'] = Cliente.objects.order_by('-id')[:10]
        return context