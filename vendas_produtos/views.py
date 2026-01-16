from django.views.generic import ListView, CreateView, DetailView, UpdateView, TemplateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth import get_user_model
from datetime import datetime
from decimal import Decimal
import calendar

from .models import VendaProduto
from .forms import VendaProdutoForm

User = get_user_model()

# --- 1. LISTAGEM (DASHBOARD) ---
class VendaProdutoListView(LoginRequiredMixin, ListView):
    model = VendaProduto
    template_name = 'vendas_produtos/lista.html'
    context_object_name = 'vendas'
    paginate_by = 20

    def get_periodo_mes_atual(self):
        """Retorna data inicial e final do mês corrente."""
        hoje = timezone.now().date()
        data_inicio = hoje.replace(day=1)
        ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
        data_fim = hoje.replace(day=ultimo_dia)
        return data_inicio, data_fim

    def get_queryset(self):
        user = self.request.user
        qs = VendaProduto.objects.all().select_related('vendedor', 'gerente')
        
        # Filtro de Data (Padrão: Mês Atual)
        data_inicio, data_fim = self.get_periodo_mes_atual()
        qs = qs.filter(data_venda__range=[data_inicio, data_fim])

        # Se não for Admin, vê apenas as suas vendas
        if not (user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN'):
            qs = qs.filter(vendedor=user)
        return qs.order_by('-data_venda', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        data_inicio, data_fim = self.get_periodo_mes_atual()
        context['periodo_inicio'] = data_inicio
        context['periodo_fim'] = data_fim

        vendas_do_mes = self.get_queryset()
        
        # Cálculos de Totais (Topo da Tela)
        if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
             # Admin: Total da Loja e Sua Própria
             minhas_vendas = VendaProduto.objects.filter(vendedor=user, data_venda__range=[data_inicio, data_fim])
             total_minha = minhas_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum']
             
             todas_vendas = VendaProduto.objects.filter(data_venda__range=[data_inicio, data_fim])
             context['total_comissao_equipe'] = todas_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
             context['total_loja'] = todas_vendas.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0
        else:
             # Vendedor: Apenas sua comissão
             total_minha = vendas_do_mes.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum']
        
        context['minha_comissao'] = total_minha or 0
        return context

# --- 2. REGISTRO DE VENDA ---
class VendaProdutoCreateView(LoginRequiredMixin, CreateView):
    model = VendaProduto
    form_class = VendaProdutoForm
    template_name = 'vendas_produtos/form.html'
    success_url = reverse_lazy('venda_produto_list')

    def get_initial(self):
        initial = super().get_initial()
        initial['data_venda'] = timezone.now().date()
        return initial

    def form_valid(self, form):
        # 1. Configura e Salva a Venda Principal (Carro ou Serviço Avulso)
        main_venda = form.instance
        main_venda.vendedor = self.request.user
        
        # O Django salva automaticamente todos os campos do Model presentes no Form
        # Isso inclui: Modelo, Placa, Cor, Ano, Valor e Pagamentos do item principal.
        response = super().form_valid(form)
        
        # 2. Processamento da Venda Casada (Apenas se for Venda de Veículo)
        if main_venda.tipo_produto == 'VENDA_VEICULO':
            adicionais_criados = 0
            
            # Função auxiliar para criar cada serviço extra selecionado no Modal
            def processar_adicional(tipo_prod, check_field, valor_field, metodo_field):
                # Verifica se o checkbox foi marcado no form
                if form.cleaned_data.get(check_field):
                    valor = form.cleaned_data.get(valor_field) or Decimal('0.00')
                    # Pega o nome do campo de pagamento escolhido no modal (ex: 'pgto_pix')
                    metodo_key = form.cleaned_data.get(metodo_field) 
                    
                    if valor > 0 and metodo_key:
                        # Cria um novo registro separado para este serviço
                        nova_venda = VendaProduto(
                            vendedor=self.request.user,
                            tipo_produto=tipo_prod,
                            # Copia TODOS os dados de identificação do carro
                            cliente_nome=main_venda.cliente_nome,
                            placa=main_venda.placa,
                            modelo_veiculo=main_venda.modelo_veiculo,
                            cor=main_venda.cor,
                            ano=main_venda.ano,
                            # Valor específico deste serviço
                            valor_venda=valor,
                            # Copia dados financeiros auxiliares (caso seja útil rastrear)
                            banco_financiamento=main_venda.banco_financiamento,
                            numero_proposta=main_venda.numero_proposta,
                            data_venda=main_venda.data_venda,
                            observacoes=f"Adicional de {main_venda.modelo_veiculo} - {main_venda.placa}. (Venda Casada)",
                            status='PENDENTE'
                        )
                        
                        # Define dinamicamente o campo de pagamento correto para este serviço
                        # Ex: Se o usuário escolheu 'Débito', faz: nova_venda.pgto_debito = valor
                        setattr(nova_venda, metodo_key, valor)
                        
                        nova_venda.save() # O Model calcula a comissão automaticamente ao salvar
                        return 1
                return 0

            # Processa os 3 tipos possíveis de adicionais
            c1 = processar_adicional('GARANTIA', 'adicional_garantia', 'valor_garantia', 'metodo_garantia')
            c2 = processar_adicional('SEGURO', 'adicional_seguro', 'valor_seguro', 'metodo_seguro')
            c3 = processar_adicional('TRANSFERENCIA', 'adicional_transferencia', 'valor_transferencia', 'metodo_transferencia')
            
            total_extras = c1 + c2 + c3

            if total_extras > 0:
                messages.success(self.request, f"Venda do Veículo registrada + {total_extras} serviços adicionais criados com sucesso!")
            else:
                messages.success(self.request, "Venda do Veículo registrada com sucesso!")
        else:
            # Caso seja Serviço Avulso (Ex: Só uma transferência)
            messages.success(self.request, "Serviço registrado com sucesso!")
            
        return response

# --- 3. EDIÇÃO ---
class VendaProdutoUpdateView(LoginRequiredMixin, UpdateView):
    model = VendaProduto
    form_class = VendaProdutoForm
    template_name = 'vendas_produtos/form.html'
    success_url = reverse_lazy('venda_produto_list')

    def dispatch(self, request, *args, **kwargs):
        venda = self.get_object()
        is_admin = request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'
        # Bloqueia edição se já aprovado (exceto Admin)
        if venda.status == 'APROVADO' and not is_admin:
            messages.error(request, "Vendas aprovadas não podem ser alteradas.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        is_admin = self.request.user.is_superuser or getattr(self.request.user.profile, 'nivel_acesso', '') == 'ADMIN'
        # Se vendedor editar, volta para PENDENTE para reavaliação do Gerente
        if not is_admin:
            form.instance.status = 'PENDENTE'
            form.instance.gerente = None
            form.instance.data_aprovacao = None
            messages.info(self.request, "Venda atualizada e retornada para análise.")
        else:
            messages.success(self.request, "Venda atualizada com sucesso.")
        return super().form_valid(form)

# --- 4. EXCLUSÃO ---
class VendaProdutoDeleteView(LoginRequiredMixin, DeleteView):
    model = VendaProduto
    template_name = 'vendas_produtos/delete_confirm.html'
    success_url = reverse_lazy('venda_produto_list')

    def dispatch(self, request, *args, **kwargs):
        venda = self.get_object()
        is_admin = request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'
        
        if venda.vendedor != request.user and not is_admin:
            messages.error(request, "Permissão negada.")
            return redirect('venda_produto_list')

        if venda.status == 'APROVADO' and not is_admin:
            messages.error(request, "Vendas APROVADAS não podem ser excluídas.")
            return redirect('venda_produto_list')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Venda excluída com sucesso.")
        return super().form_valid(form)

# --- 5. RELATÓRIOS E AÇÕES ---

class VendaProdutoPrintView(LoginRequiredMixin, DetailView):
    model = VendaProduto
    template_name = 'vendas_produtos/comprovante.html'
    context_object_name = 'venda'

class VendaProdutoRelatorioView(LoginRequiredMixin, TemplateView):
    template_name = 'vendas_produtos/relatorio.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
            messages.error(request, "Acesso negado. Apenas administradores podem ver o relatório.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filtros GET
        data_inicio_str = self.request.GET.get('data_inicio')
        data_fim_str = self.request.GET.get('data_fim')
        vendedor_id = self.request.GET.get('vendedor')

        # Datas Default (Mês Atual)
        hoje = timezone.now().date()
        if data_inicio_str:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        else:
            data_inicio = hoje.replace(day=1)
            data_inicio_str = data_inicio.strftime('%Y-%m-%d')

        if data_fim_str:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        else:
            ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
            data_fim = hoje.replace(day=ultimo_dia)
            data_fim_str = data_fim.strftime('%Y-%m-%d')

        # Queryset Base
        qs = VendaProduto.objects.filter(data_venda__range=[data_inicio, data_fim])
        if vendedor_id:
            qs = qs.filter(vendedor_id=vendedor_id)

        # Totais Gerais
        total_loja = qs.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0
        total_comissao = qs.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
        qtd_vendas = qs.count()

        # Agrupamento por Vendedor
        vendedores_ids = qs.values_list('vendedor', flat=True).distinct()
        relatorio_vendedores = []
        
        for vid in vendedores_ids:
            vendas_vendedor = qs.filter(vendedor_id=vid).select_related('vendedor', 'gerente').order_by('data_venda')
            soma_comissao = vendas_vendedor.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
            vendedor_obj = User.objects.get(pk=vid)
            
            relatorio_vendedores.append({
                'vendedor': vendedor_obj,
                'vendas': vendas_vendedor,
                'total_comissao': soma_comissao
            })

        # Contexto para o template
        context['periodo_inicio'] = data_inicio
        context['periodo_fim'] = data_fim
        context['periodo_inicio_str'] = data_inicio_str
        context['periodo_fim_str'] = data_fim_str
        context['total_geral_loja'] = total_loja
        context['total_geral_comissao'] = total_comissao
        context['qtd_vendas'] = qtd_vendas
        context['relatorio_vendedores'] = relatorio_vendedores
        context['lista_vendedores'] = User.objects.filter(vendas_produtos__isnull=False).distinct()
        context['vendedor_selecionado'] = int(vendedor_id) if vendedor_id else None

        return context

# --- AÇÕES DE APROVAÇÃO ---
def aprovar_venda_produto(request, pk):
    if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
        messages.error(request, "Permissão negada.")
        return redirect('venda_produto_list')

    venda = get_object_or_404(VendaProduto, pk=pk)

    if request.method == 'POST':
        numero_apolice = request.POST.get('numero_apolice')
        arquivo_apolice = request.FILES.get('arquivo_apolice')

        # Regra de Negócio: Garantia exige Apólice
        if venda.tipo_produto == 'GARANTIA':
            if not numero_apolice:
                messages.error(request, "Erro: Para Seguro Garantia, o Nº da Apólice é obrigatório.")
                return redirect('venda_produto_list')
            if not arquivo_apolice and not venda.arquivo_apolice:
                messages.error(request, "Erro: Para Seguro Garantia, o upload do PDF da Apólice é obrigatório.")
                return redirect('venda_produto_list')

        venda.status = 'APROVADO'
        venda.motivo_recusa = None
        venda.gerente = request.user
        venda.data_aprovacao = timezone.now()
        
        if numero_apolice: venda.numero_apolice = numero_apolice
        if arquivo_apolice: venda.arquivo_apolice = arquivo_apolice

        venda.save()
        messages.success(request, "Venda APROVADA.")
        return redirect('venda_produto_list')
    
    return redirect('venda_produto_list')

def rejeitar_venda_produto(request, pk):
    if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
        messages.error(request, "Permissão negada.")
        return redirect('venda_produto_list')
    if request.method == 'POST':
        venda = get_object_or_404(VendaProduto, pk=pk)
        venda.status = 'REJEITADO'
        venda.motivo_recusa = request.POST.get('motivo_recusa', 'Sem motivo')
        venda.gerente = request.user
        venda.data_aprovacao = timezone.now()
        venda.save()
        messages.warning(request, "Venda REJEITADA.")
    return redirect('venda_produto_list')