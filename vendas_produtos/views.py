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
from dateutil.relativedelta import relativedelta

from .models import VendaProduto, FechamentoMensal, ParametrosComissao
from .forms import VendaProdutoForm, ParametrosComissaoForm

User = get_user_model()

# --- NOVA VIEW: CONFIGURAÇÃO DE COMISSÃO (ADMIN ONLY) ---
class ConfiguracaoComissaoView(LoginRequiredMixin, UpdateView):
    model = ParametrosComissao
    form_class = ParametrosComissaoForm
    template_name = 'vendas_produtos/configuracao_comissao.html'
    success_url = reverse_lazy('configuracao_comissao')

    def get_object(self, queryset=None):
        return ParametrosComissao.get_solo()

    def dispatch(self, request, *args, **kwargs):
        # Apenas ADMIN pode acessar
        if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
            messages.error(request, "Acesso restrito ao Administrador.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Configurações de comissão atualizadas com sucesso!")
        return super().form_valid(form)

# --- VIEWS EXISTENTES ---
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
        qs = VendaProduto.objects.all().select_related('vendedor', 'gerente', 'vendedor_ajudante')
        data_inicio, data_fim = self.get_periodo_mes_atual()
        qs = qs.filter(data_venda__range=[data_inicio, data_fim])
        is_gestor = user.is_superuser or getattr(user.profile, 'nivel_acesso', '') in ['ADMIN', 'GERENTE']
        if not is_gestor:
            qs = qs.filter(Q(vendedor=user) | Q(vendedor_ajudante=user))
        return qs.order_by('-data_venda', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        data_inicio, data_fim = self.get_periodo_mes_atual()
        context['periodo_inicio'] = data_inicio
        context['periodo_fim'] = data_fim

        is_admin = user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN'
        is_gerente = getattr(user.profile, 'nivel_acesso', '') == 'GERENTE'
        is_gestor = is_admin or is_gerente

        if is_gestor:
             todas_vendas = VendaProduto.objects.filter(data_venda__range=[data_inicio, data_fim])
             soma_princ = todas_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
             soma_ajud = todas_vendas.aggregate(Sum('comissao_ajudante'))['comissao_ajudante__sum'] or 0
             context['total_comissao_equipe'] = soma_princ + soma_ajud
             if is_admin:
                 context['total_loja'] = todas_vendas.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0
             minhas_vendas = VendaProduto.objects.filter(vendedor=user, data_venda__range=[data_inicio, data_fim])
             total_minha = minhas_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum']
        else:
             qs = self.get_queryset()
             ganho_principal = qs.filter(vendedor=user).aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
             ganho_ajudante = qs.filter(vendedor_ajudante=user).aggregate(Sum('comissao_ajudante'))['comissao_ajudante__sum'] or 0
             total_minha = ganho_principal + ganho_ajudante
        
        context['minha_comissao'] = total_minha or 0
        return context

class VendaProdutoCreateView(LoginRequiredMixin, CreateView):
    model = VendaProduto
    form_class = VendaProdutoForm
    template_name = 'vendas_produtos/form.html'
    success_url = reverse_lazy('venda_produto_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial['data_venda'] = timezone.now().date()
        tipo_url = self.request.GET.get('tipo')
        if tipo_url: initial['tipo_produto'] = tipo_url
        return initial

    def form_valid(self, form):
        main_venda = form.instance
        main_venda.vendedor = self.request.user
        response = super().form_valid(form)
        
        if main_venda.tipo_produto == 'VENDA_VEICULO':
            total_extras = 0
            def processar_adicional(tipo_prod, check_field, valor_field, metodo_field, custo_field=None):
                if form.cleaned_data.get(check_field):
                    valor = form.cleaned_data.get(valor_field) or Decimal('0.00')
                    metodo_key = form.cleaned_data.get(metodo_field) 
                    custo = form.cleaned_data.get(custo_field) or Decimal('0.00') if custo_field else Decimal('0.00')
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
            if total_extras > 0: messages.success(self.request, f"Venda principal + {total_extras} adicionais registrados!")
            else: messages.success(self.request, "Venda registrada com sucesso!")
        else:
            messages.success(self.request, "Lançamento registrado com sucesso!")
        return response

class VendaProdutoUpdateView(LoginRequiredMixin, UpdateView):
    model = VendaProduto
    form_class = VendaProdutoForm
    template_name = 'vendas_produtos/form.html'
    success_url = reverse_lazy('venda_produto_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        venda = self.get_object()
        is_gestor = request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') in ['ADMIN', 'GERENTE']
        if venda.status == 'APROVADO' and not is_gestor:
            messages.error(request, "Vendas aprovadas não podem ser alteradas.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        is_gestor = self.request.user.is_superuser or getattr(self.request.user.profile, 'nivel_acesso', '') in ['ADMIN', 'GERENTE']
        if not is_gestor:
            form.instance.status = 'PENDENTE'
            form.instance.gerente = None
            form.instance.data_aprovacao = None
        messages.success(self.request, "Venda atualizada.")
        return super().form_valid(form)

class VendaProdutoDeleteView(LoginRequiredMixin, DeleteView):
    model = VendaProduto
    template_name = 'vendas_produtos/delete_confirm.html'
    success_url = reverse_lazy('venda_produto_list')

    def dispatch(self, request, *args, **kwargs):
        venda = self.get_object()
        is_gestor = request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') in ['ADMIN', 'GERENTE']
        if venda.vendedor != request.user and not is_gestor:
            messages.error(request, "Permissão negada.")
            return redirect('venda_produto_list')
        if venda.status == 'APROVADO' and not is_gestor:
            messages.error(request, "Vendas APROVADAS não podem ser excluídas.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Venda excluída.")
        return super().form_valid(form)

class VendaProdutoPrintView(LoginRequiredMixin, DetailView):
    model = VendaProduto
    template_name = 'vendas_produtos/comprovante.html'
    context_object_name = 'venda'

class VendaProdutoRelatorioView(LoginRequiredMixin, TemplateView):
    template_name = 'vendas_produtos/relatorio.html'
    
    def dispatch(self, request, *args, **kwargs):
        # MANTIDO: Apenas ADMIN tem acesso, Gerente NÃO.
        if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
            messages.error(request, "Acesso restrito ao Administrador.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_inicio_str = self.request.GET.get('data_inicio')
        data_fim_str = self.request.GET.get('data_fim')
        vendedor_id = self.request.GET.get('vendedor')

        hoje = timezone.now().date()
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else hoje.replace(day=1)
        if data_fim_str: data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        else: data_fim = data_inicio.replace(day=calendar.monthrange(data_inicio.year, data_inicio.month)[1])

        context['periodo_inicio_str'] = data_inicio.strftime('%Y-%m-%d')
        context['periodo_fim_str'] = data_fim.strftime('%Y-%m-%d')
        context['mes_fechado'] = FechamentoMensal.objects.filter(mes=data_inicio.month, ano=data_inicio.year).first()
        
        mes_anterior = data_inicio - relativedelta(months=1)
        proximo_mes = data_inicio + relativedelta(months=1)
        context['nav_anterior_inicio'] = mes_anterior.replace(day=1).strftime('%Y-%m-%d')
        context['nav_proximo_inicio'] = proximo_mes.replace(day=1).strftime('%Y-%m-%d')

        qs_base = VendaProduto.objects.filter(data_venda__range=[data_inicio, data_fim])
        if vendedor_id: qs_base = qs_base.filter(vendedor_id=vendedor_id)

        context['total_geral_loja'] = qs_base.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0
        context['total_geral_comissao'] = qs_base.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
        context['total_geral_bruto'] = qs_base.aggregate(Sum('valor_venda'))['valor_venda__sum'] or 0
        context['qtd_vendas'] = qs_base.count()

        vendedores_ids = list(set(qs_base.values_list('vendedor', flat=True)))
        relatorio_vendedores = []
        for vid in vendedores_ids:
            # Correção para garantir que o loop respeite a data e mostre apenas os dados relevantes
            vendas_vendedor = list(VendaProduto.objects.filter(vendedor_id=vid, data_venda__range=[data_inicio, data_fim]).order_by('data_venda'))
            vendedor_obj = User.objects.filter(pk=vid).first()
            if vendedor_obj and vendas_vendedor:
                relatorio_vendedores.append({
                    'vendedor': vendedor_obj,
                    'vendas': vendas_vendedor,
                    'total_comissao': sum(v.comissao_vendedor for v in vendas_vendedor)
                })
        
        relatorio_vendedores.sort(key=lambda x: x['vendedor'].get_full_name() or x['vendedor'].username)
        context['relatorio_vendedores'] = relatorio_vendedores
        context['lista_vendedores'] = User.objects.filter(id__in=set(VendaProduto.objects.values_list('vendedor', flat=True))).order_by('username')
        context['vendedor_selecionado'] = int(vendedor_id) if vendedor_id else None
        context['periodo_inicio'] = data_inicio
        context['periodo_fim'] = data_fim
        return context

def aprovar_venda_produto(request, pk):
    is_gestor = request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') in ['ADMIN', 'GERENTE']
    if not is_gestor:
        messages.error(request, "Permissão negada.")
        return redirect('venda_produto_list')

    venda = get_object_or_404(VendaProduto, pk=pk)
    
    if request.method == 'POST':
        numero_apolice = request.POST.get('numero_apolice')
        arquivo_apolice = request.FILES.get('arquivo_apolice')
        
        for campo in ['custo_base', 'valor_venda']:
            valor_str = request.POST.get(campo)
            if valor_str:
                limpo = valor_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
                try: setattr(venda, campo, Decimal(limpo))
                except: pass

        if venda.tipo_produto == 'GARANTIA':
            if not numero_apolice:
                messages.error(request, "Nº da Apólice é obrigatório para Garantia.")
                return redirect('venda_produto_list')
            if not arquivo_apolice and not venda.arquivo_apolice:
                messages.error(request, "Upload da Apólice é obrigatório para Garantia.")
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

def rejeitar_venda_produto(request, pk):
    is_gestor = request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') in ['ADMIN', 'GERENTE']
    if not is_gestor:
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

def toggle_fechamento_mes(request):
    if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
        messages.error(request, "Permissão negada.")
        return redirect('venda_produto_list')

    if request.method == 'POST':
        mes = request.POST.get('mes')
        ano = request.POST.get('ano')
        acao = request.POST.get('acao')
        if mes and ano:
            if acao == 'fechar':
                FechamentoMensal.objects.get_or_create(mes=mes, ano=ano, defaults={'responsavel': request.user})
                messages.success(request, f"Mês {mes}/{ano} FECHADO com sucesso.")
            elif acao == 'reabrir':
                FechamentoMensal.objects.filter(mes=mes, ano=ano).delete()
                messages.warning(request, f"Mês {mes}/{ano} REABERTO.")
    
    try:
        # CORREÇÃO CRÍTICA: Converte reverse_lazy para string antes de concatenar
        base_url = str(reverse_lazy('venda_produto_relatorio'))
        url = base_url + f"?data_inicio={ano}-{int(mes):02d}-01"
        return redirect(url)
    except:
        return redirect('venda_produto_list')