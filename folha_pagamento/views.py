from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone
import calendar
from datetime import date
from decimal import Decimal

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
    folhas_recentes = FolhaPagamento.objects.all().order_by('-ano', '-mes')[:15]
    
    if request.method == 'POST':
        form_folha = ProcessarFolhaForm(request.POST)
        if form_folha.is_valid():
            mes = form_folha.cleaned_data['mes']
            ano = form_folha.cleaned_data['ano']
            count = 0
            for func in funcionarios:
                folha, created = FolhaPagamento.objects.get_or_create(
                    funcionario=func, mes=mes, ano=ano,
                    defaults={'salario_base': func.salario_base}
                )
                if not folha.fechada:
                    folha.calcular_folha()
                    count += 1
            messages.success(request, f"{count} folhas calculadas para {mes}/{ano}.")
            return redirect('rh_dashboard')
    else:
        form_folha = ProcessarFolhaForm()

    return render(request, 'folha_pagamento/dashboard_rh.html', {
        'funcionarios': funcionarios,
        'folhas': folhas_recentes,
        'form_folha': form_folha
    })

@login_required
@user_passes_test(is_admin_financeiro)
def lancar_desconto(request):
    if request.method == 'POST':
        form = LancarDescontoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Desconto lançado com sucesso.")
            return redirect('rh_dashboard')
    else:
        form = LancarDescontoForm()
    
    return render(request, 'folha_pagamento/form_desconto.html', {
        'form': form, 
        'titulo': 'Lançar Débito/Desconto'
    })

@login_required
@user_passes_test(is_admin_financeiro)
def lancar_credito(request):
    if request.method == 'POST':
        form = LancarCreditoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Crédito/Bônus lançado com sucesso.")
            return redirect('rh_dashboard')
    else:
        form = LancarCreditoForm()
    
    # Reutiliza o mesmo template de formulário, mudando apenas o título
    return render(request, 'folha_pagamento/form_desconto.html', {
        'form': form, 
        'titulo': 'Lançar Crédito/Bônus'
    })

@login_required
def detalhe_folha(request, pk):
    folha = get_object_or_404(FolhaPagamento, pk=pk)
    
    # Permissão: Apenas Admin ou o próprio dono da folha
    if not is_admin_financeiro(request.user) and folha.funcionario.user != request.user:
        messages.error(request, "Acesso negado aos detalhes financeiros.")
        return redirect('dashboard')

    itens_holerite = []
    
    # === VENCIMENTOS (CRÉDITOS) ===
    
    # 1. Salário Base
    itens_holerite.append({
        'codigo': '001', 'descricao': 'SALARIO BASE', 'referencia': '30 Dias',
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
        if folha.funcionario.user.profile.nivel_acesso == 'GERENTE':
            is_gerente = True
    except: pass

    if is_gerente:
        qtd_carros_equipe = VendaProduto.objects.filter(
            data_venda__range=[data_inicio, data_fim], 
            status='APROVADO',
            tipo_produto='VENDA_VEICULO'
        ).exclude(vendedor=folha.funcionario.user).count()

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
    
    return render(request, 'folha_pagamento/detalhe_folha.html', {
        'folha': folha,
        'itens': itens_holerite,
        'total_vencimentos': total_vencimentos,
        'total_descontos': folha.total_descontos,
    })