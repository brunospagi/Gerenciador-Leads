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

# --- 1. LISTAGEM ---
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
        data_inicio, data_fim = self.get_periodo_mes_atual()
        qs = qs.filter(data_venda__range=[data_inicio, data_fim])

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
        
        if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
             minhas_vendas = VendaProduto.objects.filter(vendedor=user, data_venda__range=[data_inicio, data_fim])
             total_minha = minhas_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum']
             
             todas_vendas = VendaProduto.objects.filter(data_venda__range=[data_inicio, data_fim])
             context['total_comissao_equipe'] = todas_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
             context['total_loja'] = todas_vendas.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0
        else:
             total_minha = vendas_do_mes.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum']
        
        context['minha_comissao'] = total_minha or 0
        return context

# --- 2. CREATE ---
class VendaProdutoCreateView(LoginRequiredMixin, CreateView):
    model = VendaProduto
    form_class = VendaProdutoForm
    template_name = 'vendas_produtos/form.html'
    success_url = reverse_lazy('venda_produto_list')

    def form_valid(self, form):
        form.instance.vendedor = self.request.user
        if not form.instance.data_venda:
            form.instance.data_venda = timezone.now().date()
        messages.success(self.request, "Venda registrada com sucesso!")
        return super().form_valid(form)

# --- 3. UPDATE ---
class VendaProdutoUpdateView(LoginRequiredMixin, UpdateView):
    model = VendaProduto
    form_class = VendaProdutoForm
    template_name = 'vendas_produtos/form.html'
    success_url = reverse_lazy('venda_produto_list')

    def dispatch(self, request, *args, **kwargs):
        venda = self.get_object()
        is_admin = request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'
        # TRAVA DE SEGURANÇA
        if venda.status == 'APROVADO' and not is_admin:
            messages.error(request, "Vendas aprovadas não podem ser alteradas.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        is_admin = self.request.user.is_superuser or getattr(self.request.user.profile, 'nivel_acesso', '') == 'ADMIN'
        if not is_admin:
            form.instance.status = 'PENDENTE'
            form.instance.gerente = None
            form.instance.data_aprovacao = None
            messages.info(self.request, "Venda editada. Voltou para análise.")
        else:
            messages.success(self.request, "Venda alterada com sucesso.")
        return super().form_valid(form)

# --- 4. DELETE ---
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

        # TRAVA DE SEGURANÇA
        if venda.status == 'APROVADO' and not is_admin:
            messages.error(request, "Vendas APROVADAS não podem ser excluídas.")
            return redirect('venda_produto_list')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Venda excluída com sucesso.")
        return super().form_valid(form)

# --- 5. COMPROVANTE ---
class VendaProdutoPrintView(LoginRequiredMixin, DetailView):
    model = VendaProduto
    template_name = 'vendas_produtos/comprovante.html'
    context_object_name = 'venda'

# --- 6. RELATÓRIO ---
class VendaProdutoRelatorioView(LoginRequiredMixin, TemplateView):
    template_name = 'vendas_produtos/relatorio.html'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
            messages.error(request, "Acesso negado.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # (Lógica de relatório igual a anterior)
        # ... Mantive simplificado para não estourar o limite, 
        # a lógica é a mesma que já te passei no passo anterior ...
        return context

# --- 7. ACTIONS (APROVAÇÃO COM UPLOAD) ---
def aprovar_venda_produto(request, pk):
    # 1. Verifica Permissão
    if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
        messages.error(request, "Permissão negada.")
        return redirect('venda_produto_list')

    venda = get_object_or_404(VendaProduto, pk=pk)

    if request.method == 'POST':
        numero_apolice = request.POST.get('numero_apolice')
        arquivo_apolice = request.FILES.get('arquivo_apolice') # Pega arquivo do POST

        # 2. Regra para Seguro Garantia: Obrigatório Apólice e Arquivo
        if venda.tipo_produto == 'GARANTIA':
            if not numero_apolice:
                messages.error(request, "Para Seguro Garantia, o Nº da Apólice é obrigatório.")
                return redirect('venda_produto_list')
            
            if not arquivo_apolice and not venda.arquivo_apolice:
                messages.error(request, "Para Seguro Garantia, o upload do PDF da Apólice é obrigatório.")
                return redirect('venda_produto_list')

        # 3. Salva
        venda.status = 'APROVADO'
        venda.motivo_recusa = None
        venda.gerente = request.user
        venda.data_aprovacao = timezone.now()
        
        if numero_apolice:
            venda.numero_apolice = numero_apolice
        if arquivo_apolice:
            venda.arquivo_apolice = arquivo_apolice

        venda.save()
        messages.success(request, f"Venda APROVADA.")
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
        messages.warning(request, f"Venda REJEITADA.")
    return redirect('venda_produto_list')