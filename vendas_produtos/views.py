from django.views.generic import ListView, CreateView, DetailView, UpdateView, TemplateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
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
        hoje = timezone.now().date()
        data_inicio = hoje.replace(day=1)
        ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
        data_fim = hoje.replace(day=ultimo_dia)
        return data_inicio, data_fim

    def get_queryset(self):
        user = self.request.user
        # .distinct() adicionado para evitar duplicatas causadas por joins
        qs = VendaProduto.objects.all().select_related('vendedor', 'gerente', 'vendedor_ajudante')
        
        data_inicio, data_fim = self.get_periodo_mes_atual()
        qs = qs.filter(data_venda__range=[data_inicio, data_fim])

        # Se não for Admin, vê apenas as suas vendas OU onde é ajudante
        if not (user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN'):
            qs = qs.filter(Q(vendedor=user) | Q(vendedor_ajudante=user))
        
        return qs.order_by('-data_venda', '-id').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        data_inicio, data_fim = self.get_periodo_mes_atual()
        context['periodo_inicio'] = data_inicio
        context['periodo_fim'] = data_fim

        vendas_do_mes = self.get_queryset()
        
        if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
             # Query isolada com distinct() para garantir somas corretas
             todas_vendas = VendaProduto.objects.filter(data_venda__range=[data_inicio, data_fim]).distinct()
             
             soma_princ = todas_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
             soma_ajud = todas_vendas.aggregate(Sum('comissao_ajudante'))['comissao_ajudante__sum'] or 0
             
             context['total_comissao_equipe'] = soma_princ + soma_ajud
             context['total_loja'] = todas_vendas.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0
             
             minhas_vendas = VendaProduto.objects.filter(vendedor=user, data_venda__range=[data_inicio, data_fim]).distinct()
             total_minha = minhas_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum']
        else:
             ganho_principal = vendas_do_mes.filter(vendedor=user).aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
             ganho_ajudante = vendas_do_mes.filter(vendedor_ajudante=user).aggregate(Sum('comissao_ajudante'))['comissao_ajudante__sum'] or 0
             total_minha = ganho_principal + ganho_ajudante
        
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
        main_venda = form.instance
        main_venda.vendedor = self.request.user
        
        response = super().form_valid(form)
        
        if main_venda.tipo_produto == 'VENDA_VEICULO':
            adicionais_criados = 0
            
            def processar_adicional(tipo_prod, check_field, valor_field, metodo_field, custo_field=None):
                if form.cleaned_data.get(check_field):
                    valor = form.cleaned_data.get(valor_field) or Decimal('0.00')
                    metodo_key = form.cleaned_data.get(metodo_field) 
                    custo = Decimal('0.00')
                    if custo_field:
                         custo = form.cleaned_data.get(custo_field) or Decimal('0.00')
                    
                    if valor > 0 and metodo_key:
                        nova_venda = VendaProduto(
                            vendedor=self.request.user,
                            tipo_produto=tipo_prod,
                            cliente_nome=main_venda.cliente_nome,
                            placa=main_venda.placa,
                            modelo_veiculo=main_venda.modelo_veiculo,
                            cor=main_venda.cor,
                            ano=main_venda.ano,
                            valor_venda=valor,
                            custo_base=custo,
                            banco_financiamento=main_venda.banco_financiamento,
                            numero_proposta=main_venda.numero_proposta,
                            data_venda=main_venda.data_venda,
                            observacoes=f"Adicional de {main_venda.modelo_veiculo} - {main_venda.placa}. (Venda Casada)",
                            status='PENDENTE'
                        )
                        setattr(nova_venda, metodo_key, valor)
                        nova_venda.save()
                        return 1
                return 0

            c1 = processar_adicional('GARANTIA', 'adicional_garantia', 'valor_garantia', 'metodo_garantia')
            c2 = processar_adicional('SEGURO', 'adicional_seguro', 'valor_seguro', 'metodo_seguro')
            c3 = processar_adicional('TRANSFERENCIA', 'adicional_transferencia', 'valor_transferencia', 'metodo_transferencia', custo_field='custo_transferencia')
            
            total_extras = c1 + c2 + c3

            if total_extras > 0:
                messages.success(self.request, f"Venda do Veículo registrada + {total_extras} serviços adicionais criados com sucesso!")
            else:
                messages.success(self.request, "Venda do Veículo registrada com sucesso!")
        else:
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
        
        data_inicio_str = self.request.GET.get('data_inicio')
        data_fim_str = self.request.GET.get('data_fim')
        vendedor_id = self.request.GET.get('vendedor')

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

        # [CORREÇÃO DUPLICIDADE] - distinct() aplicado aqui
        qs_base = VendaProduto.objects.filter(data_venda__range=[data_inicio, data_fim]).distinct()
        
        if vendedor_id:
            qs_base = qs_base.filter(vendedor_id=vendedor_id)

        # Agregações
        total_loja = qs_base.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0
        total_comissao = qs_base.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
        total_bruto = qs_base.aggregate(Sum('valor_venda'))['valor_venda__sum'] or 0
        qtd_vendas = qs_base.count()

        # [CORREÇÃO] Lista de IDs únicos de vendedores
        vendedores_ids = qs_base.values_list('vendedor', flat=True).distinct()
        relatorio_vendedores = []
        
        for vid in vendedores_ids:
            # [CORREÇÃO CRÍTICA] Re-filtramos diretamente do Model para garantir limpeza
            # Isso evita herdar joins estranhos se 'qs_base' tiver sido contaminado
            vendas_vendedor = VendaProduto.objects.filter(
                vendedor_id=vid, 
                data_venda__range=[data_inicio, data_fim]
            ).select_related('vendedor', 'gerente').order_by('data_venda', 'id').distinct()
            
            soma_comissao = vendas_vendedor.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
            
            # Pega o objeto User
            vendedor_obj = User.objects.filter(pk=vid).first()
            if vendedor_obj:
                relatorio_vendedores.append({
                    'vendedor': vendedor_obj,
                    'vendas': vendas_vendedor,
                    'total_comissao': soma_comissao
                })

        context['periodo_inicio'] = data_inicio
        context['periodo_fim'] = data_fim
        context['periodo_inicio_str'] = data_inicio_str
        context['periodo_fim_str'] = data_fim_str
        
        context['total_geral_loja'] = total_loja
        context['total_geral_comissao'] = total_comissao
        context['total_geral_bruto'] = total_bruto
        context['qtd_vendas'] = qtd_vendas
        
        context['relatorio_vendedores'] = relatorio_vendedores
        # [CORREÇÃO] Lista para o filtro dropdown também única
        context['lista_vendedores'] = User.objects.filter(vendas_produtos__isnull=False).distinct()
        context['vendedor_selecionado'] = int(vendedor_id) if vendedor_id else None

        return context

def aprovar_venda_produto(request, pk):
    if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
        messages.error(request, "Permissão negada.")
        return redirect('venda_produto_list')

    venda = get_object_or_404(VendaProduto, pk=pk)

    if request.method == 'POST':
        numero_apolice = request.POST.get('numero_apolice')
        arquivo_apolice = request.FILES.get('arquivo_apolice')

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