from django.views.generic import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from clientes.models import Cliente
from .forms import LeadEntradaForm
from .logic import definir_proximo_vendedor, enviar_webhook_n8n

class PainelDistribuicaoView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = LeadEntradaForm
    template_name = 'distribuicao/painel_entrada.html'
    success_url = reverse_lazy('painel-distribuicao')

    def form_valid(self, form):
        # 1. Busca quem é o próximo da vez
        vendedor_selecionado = definir_proximo_vendedor()
        
        if not vendedor_selecionado:
            form.add_error(None, "ERRO CRÍTICO: Nenhum vendedor ativo no rodízio!")
            return self.form_invalid(form)

        # 2. Preenche os dados automáticos do Lead
        form.instance.vendedor = vendedor_selecionado
        form.instance.status_negociacao = Cliente.StatusNegociacao.NOVO
        form.instance.prioridade = Cliente.Prioridade.MORNO
        form.instance.tipo_contato = Cliente.TipoContato.MENSAGEM
        form.instance.proximo_passo = Cliente.ProximoPasso.MENSAGEM
        
        # 3. Salva no banco
        response = super().form_valid(form)
        
        # 4. Envia para o n8n
        enviar_webhook_n8n(self.object)
        
        # 5. Feedback visual
        messages.success(self.request, f"Lead cadastrado e enviado para: {vendedor_selecionado.username}")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Lista os 10 últimos para conferência visual
        context['ultimos_leads'] = Cliente.objects.order_by('-id')[:10]
        return context