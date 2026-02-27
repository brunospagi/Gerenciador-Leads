from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum

# Importe os modelos dos seus aplicativos
from vendas_produtos.models import VendaProduto
from financeiro.models import TransacaoFinanceira
from controle_ponto.models import RegistroPonto

@login_required
def admin_dashboard(request):
    # Trava de Segurança: Apenas Admin ou Gerente
    nivel = getattr(request.user.profile, 'nivel_acesso', '')
    if not request.user.is_superuser and nivel not in ['ADMIN', 'GERENTE']:
        messages.error(request, "Acesso negado. Esta área é restrita à diretoria.")
        return redirect('dashboard') # Redireciona para o portal inicial comum

    hoje = timezone.now().date()
    mes_atual = hoje.month
    ano_atual = hoje.year

    # 1. Indicadores de Vendas (Mês Atual)
    vendas_mes = VendaProduto.objects.filter(data_venda__month=mes_atual, data_venda__year=ano_atual, status='APROVADO')
    qtd_vendas = vendas_mes.count()
    lucro_bruto_vendas = vendas_mes.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0

    # 2. Indicadores Financeiros (Despesas do Mês)
    despesas_mes = TransacaoFinanceira.objects.filter(
        data_pagamento__month=mes_atual, 
        data_pagamento__year=ano_atual, 
        tipo='DESPESA', 
        efetivado=True
    )
    total_despesas = despesas_mes.aggregate(Sum('valor'))['valor__sum'] or 0

    # 3. Equipe em Loja (Quantos bateram ponto de entrada hoje)
    pontos_hoje = RegistroPonto.objects.filter(data=hoje, entrada__isnull=False).count()

    # 4. Últimas 5 Vendas para a tabela de histórico rápido
    ultimas_vendas = VendaProduto.objects.filter(status='APROVADO').order_by('-data_venda', '-id')[:5]

    context = {
        'mes_atual': mes_atual,
        'ano_atual': ano_atual,
        'qtd_vendas': qtd_vendas,
        'lucro_bruto_vendas': lucro_bruto_vendas,
        'total_despesas': total_despesas,
        'saldo_parcial': lucro_bruto_vendas - total_despesas,
        'pontos_hoje': pontos_hoje,
        'ultimas_vendas': ultimas_vendas,
    }
    
    return render(request, 'dashboard_admin.html', context)