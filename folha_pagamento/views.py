from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone
import calendar
from datetime import date
from decimal import Decimal

from .models import FolhaPagamento, Desconto, ParcelaDesconto
from funcionarios.models import Funcionario
from vendas_produtos.models import VendaProduto
from .forms import LancarDescontoForm, ProcessarFolhaForm

# === PERMISSÃO: APENAS ADMIN (Financeiro) ===
def is_admin_financeiro(user):
    # Retorna True apenas se for Superuser ou ADMIN
    # Gerentes retornam False aqui
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
    
    return render(request, 'folha_pagamento/form_desconto.html', {'form': form})

@login_required
def detalhe_folha(request, pk):
    folha = get_object_or_404(FolhaPagamento, pk=pk)
    
    # Permite se for Admin Financeiro OU se a folha for do próprio usuário logado
    if not is_admin_financeiro(request.user) and folha.funcionario.user != request.user:
        messages.error(request, "Acesso negado aos detalhes financeiros.")
        return redirect('dashboard')

    itens_holerite = []
    
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
    valor_comissao = total_vendas['comissao_vendedor__sum'] or 0
    if valor_comissao > 0:
        itens_holerite.append({
            'codigo': '050', 'descricao': 'COMISSOES DE VENDAS', 'referencia': f"{total_vendas['id__count']} Ops",
            'vencimentos': valor_comissao, 'descontos': 0
        })

    vendas_ajuda = VendaProduto.objects.filter(
        vendedor_ajudante=folha.funcionario.user,
        data_venda__range=[data_inicio, data_fim], status='APROVADO'
    )
    total_ajuda = vendas_ajuda.aggregate(Sum('comissao_ajudante'), Count('id'))
    valor_ajuda = total_ajuda['comissao_ajudante__sum'] or 0
    if valor_ajuda > 0:
        itens_holerite.append({
            'codigo': '051', 'descricao': 'COMISSOES (AJUDA)', 'referencia': f"{total_ajuda['id__count']} Ops",
            'vencimentos': valor_ajuda, 'descontos': 0
        })

    # 3. Vale Transporte (Novo)
    if folha.desconto_vt > 0:
        itens_holerite.append({
            'codigo': '105', 
            'descricao': 'VALE TRANSPORTE (LEI)', 
            'referencia': '6.00 %',
            'vencimentos': 0, 
            'descontos': folha.desconto_vt
        })

    # 4. Outros Descontos
    parcelas = ParcelaDesconto.objects.filter(
        desconto_pai__funcionario=folha.funcionario,
        mes_referencia=folha.mes, ano_referencia=folha.ano
    ).select_related('desconto_pai')

    for p in parcelas:
        desc = p.desconto_pai
        itens_holerite.append({
            'codigo': '100', 'descricao': f"{desc.get_tipo_display().upper()} - {desc.descricao[:20].upper()}",
            'referencia': f"{p.numero_parcela}/{desc.qtd_parcelas}",
            'vencimentos': 0, 'descontos': p.valor
        })

    total_vencimentos = folha.salario_base + folha.total_comissoes
    
    return render(request, 'folha_pagamento/detalhe_folha.html', {
        'folha': folha,
        'itens': itens_holerite,
        'total_vencimentos': total_vencimentos,
        'total_descontos': folha.total_descontos,
    })