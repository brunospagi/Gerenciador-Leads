from django.views.generic import ListView, CreateView, DetailView, UpdateView, TemplateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth import get_user_model
from datetime import datetime
import calendar

from .models import VendaProduto
from .forms import VendaProdutoForm

User = get_user_model()

# =============================================================================
# 1. LISTAGEM OPERACIONAL (DASHBOARD)
# - Filtra mês corrente.
# - Vendedor vê apenas as suas. Admin vê todas.
# =============================================================================
class VendaProdutoListView(LoginRequiredMixin, ListView):
    model = VendaProduto
    template_name = 'vendas_produtos/lista.html'
    context_object_name = 'vendas'
    paginate_by = 20

    def get_periodo_mes_atual(self):
        hoje = timezone.now().date()
        data_inicio = hoje.replace(day=1)
        ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
        data_fim = hoje.replace(day=ultimo_dia)
        return data_inicio, data_fim

    def get_queryset(self):
        user = self.request.user
        qs = VendaProduto.objects.all().select_related('vendedor', 'gerente')

        # 1. Filtro de Data (Mês Corrente)
        data_inicio, data_fim = self.get_periodo_mes_atual()
        qs = qs.filter(data_venda__range=[data_inicio, data_fim])

        # 2. Permissão
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

        # Minha Comissão (Pessoal)
        if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
             minhas_vendas = VendaProduto.objects.filter(vendedor=user, data_venda__range=[data_inicio, data_fim])
             total_minha = minhas_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum']
             
             # Totais Gerais (Para Admin)
             todas_vendas = VendaProduto.objects.filter(data_venda__range=[data_inicio, data_fim])
             context['total_comissao_equipe'] = todas_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
             context['total_loja'] = todas_vendas.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0
        else:
             total_minha = vendas_do_mes.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum']
        
        context['minha_comissao'] = total_minha or 0
        return context


# =============================================================================
# 2. CRIAÇÃO DE VENDA
# =============================================================================
class VendaProdutoCreateView(LoginRequiredMixin, CreateView):
    model = VendaProduto
    form_class = VendaProdutoForm
    template_name = 'vendas_produtos/form.html'
    success_url = reverse_lazy('venda_produto_list')

    def form_valid(self, form):
        form.instance.vendedor = self.request.user
        if not form.instance.data_venda:
            form.instance.data_venda = timezone.now().date()
        messages.success(self.request, "Venda registrada com sucesso! Aguardando conferência.")
        return super().form_valid(form)


# =============================================================================
# 3. EDIÇÃO DE VENDA (COM TRAVA DE SEGURANÇA)
# =============================================================================
class VendaProdutoUpdateView(LoginRequiredMixin, UpdateView):
    model = VendaProduto
    form_class = VendaProdutoForm
    template_name = 'vendas_produtos/form.html'
    success_url = reverse_lazy('venda_produto_list')

    def dispatch(self, request, *args, **kwargs):
        venda = self.get_object()
        is_admin = request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'
        
        # --- TRAVA: Se aprovado, Vendedor não mexe ---
        if venda.status == 'APROVADO' and not is_admin:
            messages.error(request, "Vendas APROVADAS não podem ser alteradas. Solicite ao gerente.")
            return redirect('venda_produto_list')
            
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        is_admin = self.request.user.is_superuser or getattr(self.request.user.profile, 'nivel_acesso', '') == 'ADMIN'
        
        # Se Vendedor editar, reseta para PENDENTE
        if not is_admin:
            form.instance.status = 'PENDENTE'
            form.instance.gerente = None
            form.instance.data_aprovacao = None
            messages.info(self.request, "Alteração realizada. A venda voltou para análise (Pendente).")
        else:
            messages.success(self.request, "Venda alterada com sucesso.")
            
        return super().form_valid(form)


# =============================================================================
# 4. EXCLUSÃO DE VENDA (COM TRAVA DE SEGURANÇA)
# =============================================================================
class VendaProdutoDeleteView(LoginRequiredMixin, DeleteView):
    model = VendaProduto
    template_name = 'vendas_produtos/delete_confirm.html'
    success_url = reverse_lazy('venda_produto_list')

    def dispatch(self, request, *args, **kwargs):
        venda = self.get_object()
        is_admin = request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'
        
        # 1. Só dono ou admin exclui
        if venda.vendedor != request.user and not is_admin:
            messages.error(request, "Permissão negada.")
            return redirect('venda_produto_list')

        # 2. --- TRAVA: Se aprovado, ninguém exclui (exceto admin forçado) ---
        if venda.status == 'APROVADO' and not is_admin:
            messages.error(request, "Vendas APROVADAS não podem ser excluídas.")
            return redirect('venda_produto_list')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Venda excluída com sucesso.")
        return super().form_valid(form)


# =============================================================================
# 5. IMPRESSÃO E RELATÓRIOS
# =============================================================================
class VendaProdutoPrintView(LoginRequiredMixin, DetailView):
    model = VendaProduto
    template_name = 'vendas_produtos/comprovante.html'
    context_object_name = 'venda'

class VendaProdutoRelatorioView(LoginRequiredMixin, TemplateView):
    template_name = 'vendas_produtos/relatorio.html'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
            messages.error(request, "Acesso negado ao relatório.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filtros
        data_inicio_str = self.request.GET.get('data_inicio')
        data_fim_str = self.request.GET.get('data_fim')
        vendedor_id = self.request.GET.get('vendedor')
        
        hoje = timezone.now().date()

        if data_inicio_str and data_fim_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            except ValueError:
                data_inicio = hoje.replace(day=1)
                ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
                data_fim = hoje.replace(day=ultimo_dia)
        else:
            data_inicio = hoje.replace(day=1)
            ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
            data_fim = hoje.replace(day=ultimo_dia)
        
        context['periodo_inicio'] = data_inicio
        context['periodo_fim'] = data_fim
        context['periodo_inicio_str'] = data_inicio.strftime('%Y-%m-%d')
        context['periodo_fim_str'] = data_fim.strftime('%Y-%m-%d')
        context['vendedor_selecionado'] = int(vendedor_id) if vendedor_id else None
        context['lista_vendedores'] = User.objects.filter(is_active=True).order_by('first_name')

        # Buscar APENAS APROVADOS
        vendas_aprovadas = VendaProduto.objects.filter(
            status='APROVADO',
            data_venda__range=[data_inicio, data_fim]
        ).select_related('vendedor', 'gerente').order_by('vendedor__username', 'data_venda')

        if vendedor_id:
            vendas_aprovadas = vendas_aprovadas.filter(vendedor_id=vendedor_id)

        # Totais e Agrupamento
        context['total_geral_comissao'] = vendas_aprovadas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
        context['total_geral_loja'] = vendas_aprovadas.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0
        context['qtd_vendas'] = vendas_aprovadas.count()

        vendedores_ids = vendas_aprovadas.values_list('vendedor', flat=True).distinct()
        lista_por_vendedor = []
        for user_id in vendedores_ids:
            vendas_user = vendas_aprovadas.filter(vendedor_id=user_id)
            lista_por_vendedor.append({
                'vendedor': vendas_user.first().vendedor,
                'vendas': vendas_user,
                'total_comissao': vendas_user.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0,
                'qtd': vendas_user.count()
            })
        
        context['relatorio_vendedores'] = lista_por_vendedor
        return context


# =============================================================================
# 6. AÇÕES DE GERÊNCIA
# =============================================================================
def aprovar_venda_produto(request, pk):
    if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
        messages.error(request, "Permissão negada.")
        return redirect('venda_produto_list')

    venda = get_object_or_404(VendaProduto, pk=pk)
    venda.status = 'APROVADO'
    venda.motivo_recusa = None
    venda.gerente = request.user
    venda.data_aprovacao = timezone.now()
    venda.save()
    messages.success(request, f"Venda APROVADA.")
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
        messages.warning(request, f"Venda REJEITADA.")
    return redirect('venda_produto_list')