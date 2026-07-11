from django.views.generic import ListView, CreateView, DetailView, UpdateView, TemplateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta
from decimal import Decimal
import calendar
from dateutil.relativedelta import relativedelta

from .models import VendaProduto, FechamentoMensal, ParametrosComissao
from .forms import VendaProdutoForm, ParametrosComissaoForm
from .ai_validacao import validar_comprovante_com_gemini
from .ai_extracao import extrair_dados_cliente_com_gemini
from documentos.pdf_utils import extract_crlv_data_with_gemini
from notificacoes.utils import notificar_usuario
from notificacoes.whatsapp import notificar_whatsapp_venda_rejeitada
from configuracoes.access import ModuleActionRequiredMixin

User = get_user_model()

TIPOS_CUSTO_ADMIN = {'VENDA_VEICULO', 'VENDA_MOTO', 'CONSIGNACAO', 'COMPRA'}

def _nivel_acesso(user):
    try:
        return getattr(user.profile, 'nivel_acesso', '')
    except Exception:
        return ''

def _is_admin_financeiro(user):
    return user.is_superuser or _nivel_acesso(user) == 'ADMIN'

def _is_gestor_financeiro(user):
    return user.is_superuser or _nivel_acesso(user) in ['ADMIN', 'GERENTE']


def _vendas_acessiveis(user):
    if _is_gestor_financeiro(user):
        return VendaProduto.objects.all()
    return VendaProduto.objects.filter(Q(vendedor=user) | Q(vendedor_ajudante=user))

def _gestores_financeiros(exclude_user=None):
    qs = User.objects.filter(Q(is_superuser=True) | Q(profile__nivel_acesso__in=['ADMIN', 'GERENTE'])).distinct()
    if exclude_user:
        qs = qs.exclude(pk=exclude_user.pk)
    return qs

def _parse_decimal_br(valor_str):
    if not valor_str:
        return None
    limpo = valor_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
    try:
        return Decimal(limpo)
    except Exception:
        return None

def _validar_comprovante_upload(venda, request):
    resultado = validar_comprovante_com_gemini(venda.comprovante)
    if resultado is None:
        return

    if resultado['valido']:
        venda.comprovante_status_ia = 'VALIDO'
    else:
        venda.comprovante_status_ia = 'INVALIDO'
        messages.warning(
            request,
            f"⚠️ Comprovante sinalizado como inválido pela IA: {resultado['motivo']}. "
            "A venda foi registrada normalmente; um gestor pode validar manualmente o comprovante."
        )
        for gestor in _gestores_financeiros(exclude_user=venda.vendedor):
            notificar_usuario(
                gestor,
                f"Comprovante de {venda.cliente_nome} sinalizado como suspeito pela IA: {resultado['motivo']}",
                url=reverse('venda_produto_list'),
                titulo="Comprovante Suspeito",
            )
    venda.comprovante_ia_observacao = resultado['motivo']
    venda.save(update_fields=['comprovante_status_ia', 'comprovante_ia_observacao'])

@login_required
@require_POST
def validar_comprovante_preview(request):
    """Verificação via AJAX no momento do upload, antes de enviar a venda."""
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)

    resultado = validar_comprovante_com_gemini(arquivo)
    if resultado is None:
        return JsonResponse({'disponivel': False})

    return JsonResponse({
        'disponivel': True,
        'valido': resultado['valido'],
        'motivo': resultado['motivo'],
    })

# --- WIZARD: NOVA VENDA COM IA (endpoints de extração) ---
@login_required
@require_POST
def venda_ia_extrair_cliente(request):
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)

    dados = extrair_dados_cliente_com_gemini(arquivo)
    if dados is None:
        return JsonResponse({'disponivel': False})

    return JsonResponse({'disponivel': True, 'dados': dados})

@login_required
@require_POST
def venda_ia_extrair_veiculo(request):
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)

    dados = extract_crlv_data_with_gemini(arquivo)
    if not dados:
        return JsonResponse({'disponivel': False})

    return JsonResponse({'disponivel': True, 'dados': dados})

# --- NOVA VIEW: CONFIGURAÇÃO DE COMISSÃO (ADMIN ONLY) ---
class ConfiguracaoComissaoView(LoginRequiredMixin, UpdateView):
    model = ParametrosComissao
    form_class = ParametrosComissaoForm
    template_name = 'vendas_produtos/configuracao_comissao.html'
    success_url = reverse_lazy('configuracao_comissao')

    def get_object(self, queryset=None):
        return ParametrosComissao.get_solo()

    def dispatch(self, request, *args, **kwargs):
        if not _is_admin_financeiro(request.user):
            messages.error(request, "Acesso restrito ao Administrador.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Configurações de comissão atualizadas com sucesso!")
        return super().form_valid(form)

# --- VIEWS EXISTENTES ---
class VendaProdutoListView(ModuleActionRequiredMixin, ListView):
    module_key = 'vendas'
    module_action = 'visualizar'
    model = VendaProduto
    template_name = 'vendas_produtos/lista.html'
    context_object_name = 'vendas'
    paginate_by = 20

    def get_periodo(self):
        data_inicio_str = self.request.GET.get('data_inicio')
        hoje = timezone.now().date()
        
        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date().replace(day=1)
            except ValueError:
                data_inicio = hoje.replace(day=1)
        else:
            data_inicio = hoje.replace(day=1)
            
        ultimo_dia = calendar.monthrange(data_inicio.year, data_inicio.month)[1]
        data_fim = data_inicio.replace(day=ultimo_dia)
        return data_inicio, data_fim

    def get_queryset(self):
        user = self.request.user
        qs = VendaProduto.objects.all().select_related('vendedor', 'gerente', 'vendedor_ajudante')
        data_inicio, data_fim = self.get_periodo()
        qs = qs.filter(data_venda__range=[data_inicio, data_fim])
        is_gestor = _is_gestor_financeiro(user)
        if not is_gestor:
            qs = qs.filter(Q(vendedor=user) | Q(vendedor_ajudante=user))
        return qs.order_by('-data_venda', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        data_inicio, data_fim = self.get_periodo()
        
        mes_anterior = data_inicio - relativedelta(months=1)
        proximo_mes = data_inicio + relativedelta(months=1)
        context['nav_anterior_inicio'] = mes_anterior.replace(day=1).strftime('%Y-%m-%d')
        context['nav_proximo_inicio'] = proximo_mes.replace(day=1).strftime('%Y-%m-%d')

        context['periodo_inicio'] = data_inicio
        context['periodo_fim'] = data_fim

        is_admin = _is_admin_financeiro(user)
        is_gerente = _nivel_acesso(user) == 'GERENTE'
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

class VendaProdutoCreateView(ModuleActionRequiredMixin, CreateView):
    module_key = 'vendas'
    module_action = 'criar'
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
        is_admin = _is_admin_financeiro(self.request.user)

        # Blindagem financeira: somente ADMIN pode definir custo de veículo.
        if (not is_admin) and main_venda.tipo_produto in TIPOS_CUSTO_ADMIN:
            main_venda.custo_base = Decimal('0.00')

        if not main_venda.vendedor_id:
            main_venda.vendedor = self.request.user

        # Guarda backend contra duplo envio acidental (duplo clique/reenvio de rede).
        janela = timezone.now() - timedelta(seconds=25)
        vendedor_ref = main_venda.vendedor
        duplicada = VendaProduto.objects.filter(
            vendedor=vendedor_ref,
            tipo_produto=main_venda.tipo_produto,
            cliente_nome=main_venda.cliente_nome,
            placa=main_venda.placa,
            data_venda=main_venda.data_venda,
            valor_venda=main_venda.valor_venda,
            data_criacao__gte=janela,
        ).exists()
        if duplicada:
            messages.warning(self.request, "Envio duplicado detectado. O lançamento já foi registrado.")
            return redirect('venda_produto_list')

        response = super().form_valid(form)

        if 'comprovante' in form.changed_data and main_venda.comprovante:
            _validar_comprovante_upload(main_venda, self.request)

        if main_venda.tipo_produto == 'VENDA_VEICULO':
            total_extras = 0
            def processar_adicional(tipo_prod, check_field, valor_field, metodo_field, custo_field=None):
                if form.cleaned_data.get(check_field):
                    valor = form.cleaned_data.get(valor_field) or Decimal('0.00')
                    metodo_key = form.cleaned_data.get(metodo_field) 
                    custo = form.cleaned_data.get(custo_field) or Decimal('0.00') if custo_field else Decimal('0.00')
                    if valor > 0 and metodo_key:
                        nova_venda = VendaProduto(
                            vendedor=main_venda.vendedor, 
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
            msg_autor = f" para {main_venda.vendedor.get_full_name() or main_venda.vendedor.username}" if self.request.user != main_venda.vendedor else ""
            if total_extras > 0: messages.success(self.request, f"Venda principal + {total_extras} adicionais registrados{msg_autor}!")
            else: messages.success(self.request, f"Venda registrada com sucesso{msg_autor}!")
        else:
            messages.success(self.request, "Lançamento registrado com sucesso!")

        for gestor in _gestores_financeiros(exclude_user=main_venda.vendedor):
            notificar_usuario(
                gestor,
                f"Nova venda de {main_venda.cliente_nome} registrada por "
                f"{main_venda.vendedor.get_full_name() or main_venda.vendedor.username}, aguardando aprovação.",
                url=reverse('venda_produto_list'),
                titulo="Nova Venda Pendente",
            )

        return response

# --- WIZARD: NOVA VENDA COM IA (fluxo completo em 3 passos) ---
# Reutiliza toda a lógica de VendaProdutoCreateView (validação, cálculo de
# comissão, guarda anti-duplo-envio, validação de comprovante por IA e
# notificações aos gestores); muda apenas o template e o destino final.
class VendaIAWizardView(VendaProdutoCreateView):
    template_name = 'vendas_produtos/venda_ia_wizard.html'

    # Campos exibidos e editáveis no Passo 3. Os demais campos do form são
    # enviados ocultos (com seus valores padrão) para não quebrar validações.
    # tipo_produto fica fora daqui de propósito: agora é escolhido no seu
    # próprio passo do wizard (cards), não na grade de campos do passo final.
    CAMPOS_VISIVEIS = [
        'cliente_nome', 'cpfCNPJ_cliente', 'rgIE_cliente', 'dtnasc_cliente', 'telCel_cliente',
        'marca_veiculo', 'modelo_veiculo', 'placa', 'cor', 'ano', 'km_veiculo',
        'com_desconto', 'valor_venda', 'data_venda',
        'pgto_pix', 'pgto_transferencia', 'pgto_debito', 'pgto_credito', 'pgto_financiamento',
        'banco_financiamento', 'numero_proposta', 'comprovante',
    ]

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault('tipo_produto', 'VENDA_VEICULO')
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['campos_visiveis'] = self.CAMPOS_VISIVEIS
        return context

    def get_success_url(self):
        if self.object:
            return f"{reverse('venda_produto_minuta', kwargs={'pk': self.object.pk})}?auto_print=1"
        return super().get_success_url()

class VendaProdutoUpdateView(ModuleActionRequiredMixin, UpdateView):
    module_key = 'vendas'
    module_action = 'editar'
    model = VendaProduto
    form_class = VendaProdutoForm
    template_name = 'vendas_produtos/form.html'
    success_url = reverse_lazy('venda_produto_list')

    def get_queryset(self):
        return _vendas_acessiveis(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        venda = self.get_object()
        is_gestor = _is_gestor_financeiro(request.user)
        if venda.status == 'APROVADO' and not is_gestor:
            messages.error(request, "Vendas aprovadas não podem ser alteradas.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        is_gestor = _is_gestor_financeiro(self.request.user)
        is_admin = _is_admin_financeiro(self.request.user)
        venda_original = self.get_object()

        # Blindagem financeira: gerente/vendedor não alteram custo de veículo.
        if (not is_admin) and form.instance.tipo_produto in TIPOS_CUSTO_ADMIN:
            form.instance.custo_base = venda_original.custo_base

        if not is_gestor:
            reenviada = venda_original.status == 'REJEITADO'
            form.instance.status = 'PENDENTE'
            form.instance.gerente = None
            form.instance.data_aprovacao = None
            form.instance.motivo_recusa = None
            if reenviada:
                messages.success(self.request, "Venda corrigida e reenviada para conferência.")
            else:
                messages.success(self.request, "Venda atualizada.")
        else:
            messages.success(self.request, "Venda atualizada.")
        response = super().form_valid(form)

        if 'comprovante' in form.changed_data:
            if venda_original.comprovante:
                venda_original.comprovante.delete(save=False)
            if form.instance.comprovante:
                _validar_comprovante_upload(form.instance, self.request)

        return response

class VendaProdutoDeleteView(ModuleActionRequiredMixin, DeleteView):
    module_key = 'vendas'
    module_action = 'excluir'
    model = VendaProduto
    template_name = 'vendas_produtos/delete_confirm.html'
    success_url = reverse_lazy('venda_produto_list')

    def get_queryset(self):
        return _vendas_acessiveis(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        venda = self.get_object()
        is_gestor = _is_gestor_financeiro(request.user)
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

class VendaProdutoPrintView(ModuleActionRequiredMixin, DetailView):
    module_key = 'vendas'
    module_action = 'visualizar'
    model = VendaProduto
    template_name = 'vendas_produtos/comprovante.html'
    context_object_name = 'venda'

    def get_queryset(self):
        return _vendas_acessiveis(self.request.user)

class VendaProdutoMinutaPrintView(ModuleActionRequiredMixin, DetailView):
    module_key = 'vendas'
    module_action = 'visualizar'
    model = VendaProduto
    template_name = 'vendas_produtos/minuta.html'
    context_object_name = 'venda'

    def get_queryset(self):
        return _vendas_acessiveis(self.request.user)

    def _formas_pagamento_extenso(self, venda):
        formas = []
        if (venda.pgto_pix or 0) > 0:
            formas.append(f"Pix (R$ {venda.pgto_pix:.2f})")
        if (venda.pgto_transferencia or 0) > 0:
            formas.append(f"Transferência (R$ {venda.pgto_transferencia:.2f})")
        if (venda.pgto_debito or 0) > 0:
            formas.append(f"Débito (R$ {venda.pgto_debito:.2f})")
        if (venda.pgto_credito or 0) > 0:
            formas.append(f"Crédito (R$ {venda.pgto_credito:.2f})")
        if (venda.pgto_financiamento or 0) > 0:
            formas.append(f"Financiamento (R$ {venda.pgto_financiamento:.2f})")
        return " + ".join(formas) if formas else "Não informado"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        venda = context['venda']
        dtnasc_cliente = (venda.dtnasc_cliente or '').strftime('%d/%m/%Y') if venda.dtnasc_cliente else 'Não informado'
        modelo = (venda.modelo_veiculo or '').strip()
        marca_veiculo = (venda.marca_veiculo or '').strip()
        if not marca_veiculo and modelo:
            marca_veiculo = modelo.split(' ')[0]
        origem = (venda.origem_cliente or '').upper()
        context['marca_veiculo'] = marca_veiculo
        context['formas_pagamento_extenso'] = self._formas_pagamento_extenso(venda)
        context['origem_flags'] = {
            'OLX': origem == 'OLX',
            'SOCARRAO': origem == 'LOJA',
            'SITE': origem == 'SITE',
            'FACEBOOK': origem == 'FACEBOOK',
            'WHATSAPP': origem == 'WHATSAPP',
            'OUTRO': origem == 'OUTRO',
            'INDICACAO': origem == 'INDICACAO',
            'REDES_VENDEDOR': origem == 'INSTAGRAM',
        }
        context['dtnasc_cliente'] = dtnasc_cliente
        context['auto_print'] = self.request.GET.get('auto_print') == '1'
        return context

class VendaProdutoRelatorioView(LoginRequiredMixin, TemplateView):
    template_name = 'vendas_produtos/relatorio.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not _is_admin_financeiro(request.user):
            messages.error(request, "Acesso restrito ao Administrador.")
            return redirect('venda_produto_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_inicio_str = self.request.GET.get('data_inicio')
        data_fim_str = self.request.GET.get('data_fim')
        vendedor_id_filter = self.request.GET.get('vendedor')

        hoje = timezone.now().date()
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else hoje.replace(day=1)
        except (TypeError, ValueError):
            data_inicio = hoje.replace(day=1)
        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                data_fim = data_inicio.replace(day=calendar.monthrange(data_inicio.year, data_inicio.month)[1])
        else:
            data_fim = data_inicio.replace(day=calendar.monthrange(data_inicio.year, data_inicio.month)[1])

        context['periodo_inicio_str'] = data_inicio.strftime('%Y-%m-%d')
        context['periodo_fim_str'] = data_fim.strftime('%Y-%m-%d')
        context['mes_fechado'] = FechamentoMensal.objects.filter(mes=data_inicio.month, ano=data_inicio.year).first()
        
        mes_anterior = data_inicio - relativedelta(months=1)
        proximo_mes = data_inicio + relativedelta(months=1)
        context['nav_anterior_inicio'] = mes_anterior.replace(day=1).strftime('%Y-%m-%d')
        context['nav_proximo_inicio'] = proximo_mes.replace(day=1).strftime('%Y-%m-%d')

        # Base Query
        qs_base = VendaProduto.objects.filter(data_venda__range=[data_inicio, data_fim])
        
        # Filtro de Vendedor (Opcional)
        if vendedor_id_filter:
            vid = int(vendedor_id_filter)
            qs_base = qs_base.filter(Q(vendedor_id=vid) | Q(vendedor_ajudante_id=vid))

        # --- TOTAIS GERAIS ---
        context['total_geral_loja'] = qs_base.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0
        
        total_comissao_titular = qs_base.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
        total_comissao_ajudante = qs_base.aggregate(Sum('comissao_ajudante'))['comissao_ajudante__sum'] or 0
        context['total_geral_comissao'] = total_comissao_titular + total_comissao_ajudante

        context['total_geral_bruto'] = qs_base.aggregate(Sum('valor_venda'))['valor_venda__sum'] or 0
        context['qtd_vendas'] = qs_base.count()

        # --- LÓGICA DE AGRUPAMENTO POR VENDEDOR ---
        if vendedor_id_filter:
            ids_para_processar = [int(vendedor_id_filter)]
        else:
            ids_titulares = set(qs_base.values_list('vendedor', flat=True))
            ids_ajudantes = set(qs_base.values_list('vendedor_ajudante', flat=True))
            ids_para_processar = list(ids_titulares | ids_ajudantes)
            if None in ids_para_processar: ids_para_processar.remove(None)
        
        # Adiciona o próprio usuário logado se ele for admin/gerente e não tiver vendas
        if not vendedor_id_filter:
            if self.request.user.id not in ids_para_processar and _is_gestor_financeiro(self.request.user):
                ids_para_processar.append(self.request.user.id)

        relatorio_vendedores = []
        
        def _chave_exibicao_venda(venda, vendedor_id):
            papel = 'GERENCIA'
            if not getattr(venda, 'is_comissao_gerente', False):
                papel = 'AJUDA' if venda.vendedor_ajudante_id == vendedor_id else 'TITULAR'
            return (
                venda.data_venda,
                venda.tipo_produto,
                (venda.cliente_nome or '').strip().lower(),
                (venda.placa or '').strip().upper(),
                (venda.modelo_veiculo or '').strip().lower(),
                Decimal(venda.valor_venda or 0),
                papel,
            )
        
        for vid in ids_para_processar:
            vendedor_obj = User.objects.filter(pk=vid).first()
            if vendedor_obj:
                # 1. Vendas como Titular
                vendas_titular = qs_base.filter(vendedor_id=vid)
                soma_titular = vendas_titular.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0
                
                # 2. Vendas como Ajudante
                vendas_ajudante = qs_base.filter(vendedor_ajudante_id=vid)
                soma_ajudante = vendas_ajudante.aggregate(Sum('comissao_ajudante'))['comissao_ajudante__sum'] or 0
                
                # Evita duplicidade no mesmo bloco do vendedor.
                todas_vendas = list(vendas_titular)
                ids_vendas = {v.id for v in todas_vendas}
                for v in vendas_ajudante:
                    if v.id not in ids_vendas:
                        todas_vendas.append(v)
                        ids_vendas.add(v.id)
                
                total_geral = Decimal('0.00')

                # 3. Se for EXCLUSIVAMENTE GERENTE, busca vendas da equipe (ADMIN fica de fora)
                is_gerente_row = False
                try:
                    if vendedor_obj.profile.nivel_acesso == 'GERENTE':
                        is_gerente_row = True
                except: pass

                if is_gerente_row:
                    vendas_equipe = (
                        qs_base.filter(
                            status='APROVADO',
                            tipo_produto__in=['VENDA_VEICULO', 'VENDA_MOTO']
                        )
                        .exclude(Q(vendedor=vendedor_obj) | Q(vendedor_ajudante=vendedor_obj))
                        .exclude(vendedor__is_superuser=True)
                        .exclude(vendedor__profile__nivel_acesso__in=['ADMIN', 'GERENTE'])
                    )
                    
                    for v in vendas_equipe:
                        if v.id in ids_vendas:
                            continue
                        v.is_comissao_gerente = True
                        if v.tipo_produto == 'VENDA_VEICULO':
                            v.valor_comissao_gerente = Decimal('150.00')
                        else:
                            v.valor_comissao_gerente = Decimal('80.00')
                        
                        todas_vendas.append(v)
                        ids_vendas.add(v.id)

                # Ordena tudo por data
                todas_vendas.sort(key=lambda x: x.data_venda)

                # Blindagem final: remove duplicidades por chave de exibição
                # (casos de dados repetidos/inconsistentes no período).
                vendas_unicas = []
                chaves_vendas = set()
                for venda in todas_vendas:
                    chave = _chave_exibicao_venda(venda, vid)
                    if chave in chaves_vendas:
                        continue
                    chaves_vendas.add(chave)
                    vendas_unicas.append(venda)

                    if getattr(venda, 'is_comissao_gerente', False):
                        total_geral += getattr(venda, 'valor_comissao_gerente', Decimal('0.00')) or Decimal('0.00')
                    elif venda.vendedor_ajudante_id == vid:
                        total_geral += venda.comissao_ajudante or Decimal('0.00')
                    else:
                        total_geral += venda.comissao_vendedor or Decimal('0.00')

                if vendas_unicas:
                    relatorio_vendedores.append({
                        'vendedor': vendedor_obj,
                        'vendas': vendas_unicas,
                        'total_comissao': total_geral
                    })
        
        relatorio_vendedores.sort(key=lambda x: x['vendedor'].get_full_name() or x['vendedor'].username)
        context['relatorio_vendedores'] = relatorio_vendedores
        context['lista_vendedores'] = User.objects.filter(id__in=ids_para_processar).order_by('username')
        context['vendedor_selecionado'] = int(vendedor_id_filter) if vendedor_id_filter else None
        context['periodo_inicio'] = data_inicio
        context['periodo_fim'] = data_fim
        return context

@login_required
@require_POST
def aprovar_venda_produto(request, pk):
    is_gestor = _is_gestor_financeiro(request.user)
    is_admin = _is_admin_financeiro(request.user)
    if not is_gestor:
        messages.error(request, "Permissão negada.")
        return redirect('venda_produto_list')

    venda = get_object_or_404(VendaProduto, pk=pk)
    
    if request.method == 'POST':
        numero_apolice = request.POST.get('numero_apolice')
        arquivo_apolice = request.FILES.get('arquivo_apolice')
        
        valor_venda = _parse_decimal_br(request.POST.get('valor_venda'))
        if valor_venda is not None:
            venda.valor_venda = valor_venda

        custo_post = _parse_decimal_br(request.POST.get('custo_base'))
        if custo_post is not None and venda.tipo_produto in TIPOS_CUSTO_ADMIN:
            if is_admin:
                venda.custo_base = custo_post
            else:
                messages.warning(
                    request,
                    "Somente ADMIN pode alterar o custo do veículo. Aprovação mantida com o custo atual."
                )

        if venda.tipo_produto in ['VENDA_VEICULO', 'VENDA_MOTO'] and (venda.valor_venda or Decimal('0.00')) <= 0:
            messages.error(request, "Valor de venda inválido. Informe um valor maior que zero para aprovar.")
            return redirect('venda_produto_list')

        if venda.tipo_produto in TIPOS_CUSTO_ADMIN and (venda.custo_base or Decimal('0.00')) <= 0:
            if is_admin:
                messages.error(request, "Custo do veículo é obrigatório para aprovação.")
            else:
                messages.error(request, "Custo do veículo está pendente. Solicite ajuste ao ADMIN antes de aprovar.")
            return redirect('venda_produto_list')

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
        
        arquivo_apolice_antigo = venda.arquivo_apolice
        if numero_apolice: venda.numero_apolice = numero_apolice
        if arquivo_apolice: venda.arquivo_apolice = arquivo_apolice

        venda.save()

        if arquivo_apolice and arquivo_apolice_antigo:
            arquivo_apolice_antigo.delete(save=False)

        notificar_usuario(
            venda.vendedor,
            f"Sua venda de {venda.cliente_nome} foi aprovada.",
            url=reverse('venda_produto_list'),
            titulo="Venda Aprovada",
        )

        messages.success(request, "Venda APROVADA.")
    return redirect(f"{reverse('venda_produto_minuta', kwargs={'pk': venda.pk})}?auto_print=1")


@login_required
@require_POST
def ajustar_custo_veiculo(request, pk):
    if not _is_admin_financeiro(request.user):
        messages.error(request, "Somente ADMIN pode ajustar custo de veículo.")
        return redirect('venda_produto_list')

    venda = get_object_or_404(VendaProduto, pk=pk)
    if venda.tipo_produto not in TIPOS_CUSTO_ADMIN:
        messages.error(request, "Este tipo de lançamento não permite ajuste de custo de veículo.")
        return redirect('venda_produto_list')

    novo_custo = _parse_decimal_br(request.POST.get('custo_base'))
    if novo_custo is None or novo_custo <= 0:
        messages.error(request, "Informe um custo válido maior que zero.")
        return redirect('venda_produto_list')

    custo_anterior = venda.custo_base or Decimal('0.00')
    venda.custo_base = novo_custo
    venda.save()

    messages.success(
        request,
        f"Custo ajustado com sucesso: de R$ {custo_anterior:.2f} para R$ {novo_custo:.2f}."
    )
    return redirect('venda_produto_list')

@login_required
@require_POST
def rejeitar_venda_produto(request, pk):
    is_gestor = _is_gestor_financeiro(request.user)
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

        notificar_usuario(
            venda.vendedor,
            f"Sua venda de {venda.cliente_nome} foi rejeitada: {venda.motivo_recusa}",
            url=reverse('venda_produto_update', kwargs={'pk': venda.pk}),
            titulo="Venda Rejeitada",
        )
        notificar_whatsapp_venda_rejeitada(venda)

        messages.warning(request, "Venda REJEITADA.")
    return redirect('venda_produto_list')

@login_required
@require_POST
def validar_comprovante_manual(request, pk):
    if not _is_gestor_financeiro(request.user):
        messages.error(request, "Permissão negada.")
        return redirect('venda_produto_list')

    venda = get_object_or_404(VendaProduto, pk=pk)
    if not venda.comprovante:
        messages.error(request, "Esta venda não possui comprovante para validar.")
        return redirect('venda_produto_list')

    venda.comprovante_status_ia = 'MANUAL'
    venda.comprovante_validado_manual_por = request.user
    venda.comprovante_validado_manual_em = timezone.now()
    venda.save(update_fields=['comprovante_status_ia', 'comprovante_validado_manual_por', 'comprovante_validado_manual_em'])
    messages.success(request, "Comprovante validado manualmente.")
    return redirect('venda_produto_list')

@login_required
@require_POST
def toggle_fechamento_mes(request):
    if not _is_admin_financeiro(request.user):
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
        base_url = str(reverse_lazy('venda_produto_relatorio'))
        url = base_url + f"?data_inicio={ano}-{int(mes):02d}-01"
        return redirect(url)
    except:
        return redirect('venda_produto_list')


