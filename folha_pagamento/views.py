from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
import calendar
from datetime import datetime, date
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.views.decorators.http import require_POST
from django.urls import reverse
from .models import FolhaPagamento, Desconto, ParcelaDesconto, Credito, ParcelaCredito
from funcionarios.models import Funcionario
from vendas_produtos.models import VendaProduto
from .forms import LancarDescontoForm, LancarCreditoForm, ProcessarFolhaForm

def is_admin_financeiro(user):
    # Retorna True se for Superuser ou se tiver perfil ADMIN
    if user.is_superuser: return True
    return getattr(user.profile, 'nivel_acesso', '') == 'ADMIN'

@login_required
@user_passes_test(is_admin_financeiro)
def dashboard_rh(request):
    funcionarios = Funcionario.objects.filter(ativo=True)
    hoje = timezone.now()

    def _resolve_mes_ano(source):
        form = ProcessarFolhaForm(source)
        if form.is_valid():
            return form.cleaned_data['mes'], form.cleaned_data['ano']
        return hoje.month, hoje.year

    if request.method == 'POST':
        mes, ano = _resolve_mes_ano(request.POST)
    else:
        mes, ano = _resolve_mes_ano(request.GET)

    folhas_mes = (
        FolhaPagamento.objects.filter(mes=mes, ano=ano)
        .select_related('funcionario', 'funcionario__user')
        .order_by('funcionario__user__first_name', 'funcionario__user__last_name')
    )

    if request.method == 'POST':
        form_folha = ProcessarFolhaForm(request.POST)
        if form_folha.is_valid():
            mes = form_folha.cleaned_data['mes']
            ano = form_folha.cleaned_data['ano']
            acao = (request.POST.get('acao') or 'calcular').strip().lower()

            if acao == 'fechar_mes':
                count_fechadas = 0
                for func in funcionarios:
                    folha, _ = FolhaPagamento.objects.get_or_create(
                        funcionario=func, mes=mes, ano=ano,
                        defaults={'salario_base': func.salario_base}
                    )
                    if not folha.fechada:
                        folha.fechar()
                        count_fechadas += 1
                messages.success(request, f"{count_fechadas} folhas fechadas para {mes:02d}/{ano}.")

            elif acao == 'pagar_mes':
                count_pagas = 0
                for func in funcionarios:
                    folha, _ = FolhaPagamento.objects.get_or_create(
                        funcionario=func, mes=mes, ano=ano,
                        defaults={'salario_base': func.salario_base}
                    )
                    if not folha.fechada:
                        folha.fechar()
                    if not folha.pago:
                        folha.pago = True
                        folha.save(update_fields=['pago'])
                        count_pagas += 1
                messages.success(request, f"{count_pagas} folhas marcadas como pagas para {mes:02d}/{ano}.")

            else:
                count = 0
                for func in funcionarios:
                    folha, _ = FolhaPagamento.objects.get_or_create(
                        funcionario=func, mes=mes, ano=ano,
                        defaults={'salario_base': func.salario_base}
                    )
                    if not folha.fechada:
                        folha.calcular_folha()
                        count += 1
                messages.success(request, f"{count} folhas calculadas para {mes:02d}/{ano}.")

            return redirect(f"{reverse('rh_dashboard')}?mes={mes}&ano={ano}")
    else:
        form_folha = ProcessarFolhaForm(initial={'mes': mes, 'ano': ano})

    return render(request, 'folha_pagamento/dashboard_rh.html', {
        'funcionarios': funcionarios,
        'folhas': folhas_mes,
        'form_folha': form_folha,
        'mes_referencia': mes,
        'ano_referencia': ano,
        'total_folhas': folhas_mes.count(),
        'total_fechadas': folhas_mes.filter(fechada=True).count(),
        'total_pagas': folhas_mes.filter(pago=True).count(),
    })

@login_required
@user_passes_test(is_admin_financeiro)
def lancar_desconto(request):
    if request.method == 'POST':
        form = LancarDescontoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Desconto lançado com sucesso.")
            return redirect('rh_lista_lancamentos') # Redireciona para a lista
    else:
        form = LancarDescontoForm()
    
    return render(request, 'folha_pagamento/form_desconto.html', {
        'form': form, 
        'titulo': 'Lançar Débito/Desconto',
        'cor_card': 'danger',      # Define cor Vermelha
        'icone': 'fa-minus-circle',
        'btn_label': 'Confirmar Desconto'
    })

@login_required
@user_passes_test(is_admin_financeiro)
def lancar_credito(request):
    if request.method == 'POST':
        form = LancarCreditoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Crédito/Bônus lançado com sucesso.")
            return redirect('rh_lista_lancamentos') # Redireciona para a lista
    else:
        form = LancarCreditoForm()
    
    # Reutiliza o template, mas muda as cores e textos
    return render(request, 'folha_pagamento/form_desconto.html', {
        'form': form, 
        'titulo': 'Lançar Crédito/Bônus',
        'cor_card': 'success',     # Define cor Verde
        'icone': 'fa-plus-circle',
        'btn_label': 'Confirmar Crédito'
    })

@login_required
@user_passes_test(is_admin_financeiro)
def lista_lancamentos_manuais(request):
    # Filtro de Data
    data_inicio_str = request.GET.get('data_inicio')
    hoje = timezone.now().date()
    
    if data_inicio_str:
        try:
            data_referencia = datetime.strptime(data_inicio_str, '%Y-%m-%d').date().replace(day=1)
        except ValueError:
            data_referencia = hoje.replace(day=1)
    else:
        data_referencia = hoje.replace(day=1)

    mes = data_referencia.month
    ano = data_referencia.year

    # Navegação
    mes_anterior = data_referencia - relativedelta(months=1)
    proximo_mes = data_referencia + relativedelta(months=1)

    # Buscando as PARCELAS que caem neste mês (pois é isso que vai pra folha)
    descontos = ParcelaDesconto.objects.filter(
        mes_referencia=mes, 
        ano_referencia=ano
    ).select_related('desconto_pai', 'desconto_pai__funcionario')

    creditos = ParcelaCredito.objects.filter(
        mes_referencia=mes, 
        ano_referencia=ano
    ).select_related('credito_pai', 'credito_pai__funcionario')

    total_descontos = descontos.aggregate(Sum('valor'))['valor__sum'] or 0
    total_creditos = creditos.aggregate(Sum('valor'))['valor__sum'] or 0

    return render(request, 'folha_pagamento/lista_lancamentos.html', {
        'descontos': descontos,
        'creditos': creditos,
        'total_descontos': total_descontos,
        'total_creditos': total_creditos,
        'data_referencia': data_referencia,
        'nav_anterior': mes_anterior.strftime('%Y-%m-%d'),
        'nav_proximo': proximo_mes.strftime('%Y-%m-%d'),
    })

@login_required
def detalhe_folha(request, pk):
    folha = get_object_or_404(FolhaPagamento, pk=pk)
    
    # Permissão: Apenas Admin ou o próprio dono da folha
    if not is_admin_financeiro(request.user) and folha.funcionario.user != request.user:
        messages.error(request, "Acesso negado aos detalhes financeiros.")
        return redirect('rh_dashboard')

    # --- FORÇA O RECÁLCULO PARA ATUALIZAR VALORES (SE A FOLHA ESTIVER ABERTA) ---
    if not folha.fechada:
        folha.calcular_folha()
        folha.refresh_from_db() 

    itens_holerite = []
    dias_salario_ref = folha.get_dias_trabalhados_mes()
    
    # === VENCIMENTOS (CRÉDITOS) ===
    
    # 1. Salário Base
    itens_holerite.append({
        'codigo': '001', 'descricao': 'SALARIO BASE', 'referencia': f'{dias_salario_ref} Dias',
        'vencimentos': folha.salario_base, 'descontos': 0
    })

    # 2. Comissões
    ultimo_dia = calendar.monthrange(folha.ano, folha.mes)[1]
    data_inicio = date(folha.ano, folha.mes, 1)
    data_fim = date(folha.ano, folha.mes, ultimo_dia)

    vendas = VendaProduto.objects.filter(
        vendedor=folha.funcionario.user,
        data_venda__range=[data_inicio, data_fim], status='APROVADO'
    )
    total_vendas = vendas.aggregate(Sum('comissao_vendedor'), Count('id'))
    val_vendas = total_vendas['comissao_vendedor__sum'] or 0
    if val_vendas > 0:
        itens_holerite.append({
            'codigo': '050', 'descricao': 'COMISSOES DE VENDAS', 'referencia': f"{total_vendas['id__count']} Ops",
            'vencimentos': val_vendas, 'descontos': 0
        })

    vendas_ajuda = VendaProduto.objects.filter(
        vendedor_ajudante=folha.funcionario.user,
        data_venda__range=[data_inicio, data_fim], status='APROVADO'
    )
    total_ajuda = vendas_ajuda.aggregate(Sum('comissao_ajudante'), Count('id'))
    val_ajuda = total_ajuda['comissao_ajudante__sum'] or 0
    if val_ajuda > 0:
        itens_holerite.append({
            'codigo': '051', 'descricao': 'COMISSOES (AJUDA)', 'referencia': f"{total_ajuda['id__count']} Ops",
            'vencimentos': val_ajuda, 'descontos': 0
        })

    # === CÁLCULO VISUAL DE COMISSÃO DE GERÊNCIA ===
    is_gerente = False
    try:
        nivel = folha.funcionario.user.profile.nivel_acesso
        if nivel == 'GERENTE':
            is_gerente = True
    except: pass

    if is_gerente:
        # Conta Vendas da Equipe (Carros)
        qtd_carros_equipe = VendaProduto.objects.filter(
            data_venda__range=[data_inicio, data_fim], 
            status='APROVADO',
            tipo_produto='VENDA_VEICULO'
        ).exclude(vendedor=folha.funcionario.user).count()

        # Conta Vendas da Equipe (Motos)
        qtd_motos_equipe = VendaProduto.objects.filter(
            data_venda__range=[data_inicio, data_fim], 
            status='APROVADO',
            tipo_produto='VENDA_MOTO'
        ).exclude(vendedor=folha.funcionario.user).count()

        val_gerencia = (qtd_carros_equipe * Decimal('150.00')) + (qtd_motos_equipe * Decimal('80.00'))

        if val_gerencia > 0:
            itens_holerite.append({
                'codigo': '060', 
                'descricao': 'COMISSÃO GERÊNCIA (EQUIPE)', 
                'referencia': f"{qtd_carros_equipe} Car / {qtd_motos_equipe} Moto",
                'vencimentos': val_gerencia, 
                'descontos': 0
            })
    # ===============================================

    # 3. Auxílio Transporte (Crédito)
    if folha.credito_vt > 0:
        dias_uteis = folha.get_dias_uteis_vt()
        itens_holerite.append({
            'codigo': '055', 'descricao': 'AUXILIO TRANSPORTE', 'referencia': f"{dias_uteis} Dias",
            'vencimentos': folha.credito_vt, 'descontos': 0
        })

    # 4. Créditos Manuais (Bônus, etc)
    creditos_manuais = ParcelaCredito.objects.filter(
        credito_pai__funcionario=folha.funcionario,
        mes_referencia=folha.mes, ano_referencia=folha.ano
    ).select_related('credito_pai')
    
    for c in creditos_manuais:
        pai = c.credito_pai
        itens_holerite.append({
            'codigo': '090', 'descricao': f"{pai.get_tipo_display().upper()} - {pai.descricao[:20].upper()}",
            'referencia': f"{c.numero_parcela}/{pai.qtd_parcelas}",
            'vencimentos': c.valor, 'descontos': 0
        })

    # === DESCONTOS (DÉBITOS) ===

    # 5. Vale Transporte (Desconto Parte Funcionário 6%)
    if folha.desconto_vt > 0:
        itens_holerite.append({
            'codigo': '105', 'descricao': 'DESC. VALE TRANSPORTE', 'referencia': '6.00 %',
            'vencimentos': 0, 'descontos': folha.desconto_vt
        })

    # 6. Descontos Manuais
    parcelas_desc = ParcelaDesconto.objects.filter(
        desconto_pai__funcionario=folha.funcionario,
        mes_referencia=folha.mes, ano_referencia=folha.ano
    ).select_related('desconto_pai')

    for p in parcelas_desc:
        desc = p.desconto_pai
        itens_holerite.append({
            'codigo': '100', 'descricao': f"{desc.get_tipo_display().upper()} - {desc.descricao[:20].upper()}",
            'referencia': f"{p.numero_parcela}/{desc.qtd_parcelas}",
            'vencimentos': 0, 'descontos': p.valor
        })

    # Totalizadores para exibição
    total_vencimentos = folha.salario_base + folha.total_comissoes + folha.credito_vt + folha.total_creditos_manuais

    # Conferencia detalhada de comissoes (incluindo split de ajuda).
    vendas_periodo = VendaProduto.objects.filter(
        data_venda__range=[data_inicio, data_fim],
        status='APROVADO',
    ).filter(
        Q(vendedor=folha.funcionario.user) | Q(vendedor_ajudante=folha.funcionario.user)
    ).select_related('vendedor', 'vendedor_ajudante')

    conferencias_comissoes = []
    total_conferencia_minha = Decimal('0.00')
    total_conferencia_outro = Decimal('0.00')
    for venda in vendas_periodo:
        sou_titular = venda.vendedor_id == folha.funcionario.user.id
        minha_comissao = venda.comissao_vendedor if sou_titular else venda.comissao_ajudante
        comissao_outro = venda.comissao_ajudante if sou_titular else venda.comissao_vendedor
        outro_usuario = venda.vendedor_ajudante if sou_titular else venda.vendedor
        meu_papel = 'Titular' if sou_titular else 'Ajudante'
        conferencias_comissoes.append({
            'data_venda': venda.data_venda,
            'cliente_nome': venda.cliente_nome,
            'tipo_produto': venda.get_tipo_produto_display(),
            'papel': meu_papel,
            'minha_comissao': minha_comissao or Decimal('0.00'),
            'comissao_outro': comissao_outro or Decimal('0.00'),
            'outro_nome': (outro_usuario.get_full_name() or outro_usuario.username) if outro_usuario else '-',
        })
        total_conferencia_minha += minha_comissao or Decimal('0.00')
        total_conferencia_outro += comissao_outro or Decimal('0.00')

    return render(request, 'folha_pagamento/detalhe_folha.html', {
        'folha': folha,
        'itens': itens_holerite,
        'total_vencimentos': total_vencimentos,
        'total_descontos': folha.total_descontos,
        'conferencias_comissoes': conferencias_comissoes,
        'total_conferencia_minha': total_conferencia_minha,
        'total_conferencia_outro': total_conferencia_outro,
    })

@login_required
@user_passes_test(is_admin_financeiro)
@require_POST
def fechar_folha(request, pk):
    # Busca a folha específica
    folha = get_object_or_404(FolhaPagamento, pk=pk)
    
    if folha.fechada:
        messages.warning(request, "Esta folha já encontra-se fechada.")
    else:
        # Chama a função que você já criou no models.py
        folha.fechar()
        messages.success(request, f"Folha de {folha.funcionario.user.first_name} ({folha.mes}/{folha.ano}) fechada com sucesso! Os valores foram travados.")
        
    # Redireciona de volta para a tela de detalhes da folha
    return redirect('rh_detalhe_folha', pk=folha.pk)
