# distribuicao/views.py
from django.views.generic import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
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
        # 1. Distribuição Automática (Round-Robin)
        vendedor_selecionado = definir_proximo_vendedor()
        
        if not vendedor_selecionado:
            form.add_error(None, "Nenhum vendedor disponível no rodízio!")
            return self.form_invalid(form)

        # Atribui o vendedor ao objeto ANTES de salvar no banco
        form.instance.vendedor = vendedor_selecionado
        
        # Define outros campos obrigatórios do seu model com valores padrão para leads novos
        form.instance.status_negociacao = Cliente.StatusNegociacao.NOVO
        form.instance.prioridade = Cliente.Prioridade.MORNO
        form.instance.tipo_contato = Cliente.TipoContato.MENSAGEM # Padrão inicial
        form.instance.proximo_passo = Cliente.ProximoPasso.MENSAGEM
        
        # Salva o cliente
        response = super().form_valid(form)
        
        # 2. Envio para Webhook (Após salvar, para termos o ID)
        enviar_webhook_n8n(self.object)
        
        messages.success(self.request, f"Lead distribuído para: {vendedor_selecionado.username}")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Mostra os últimos 10 leads distribuídos para controle visual
        context['ultimos_leads'] = Cliente.objects.order_by('-id')[:10]
        return context