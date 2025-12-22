from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum

# Importe os modelos dos seus apps
from financiamentos.models import Ficha
from vendas_produtos.models import VendaProduto

@login_required
def home(request):
    user = request.user
    hoje = timezone.now()
    mes_atual = hoje.month
    ano_atual = hoje.year

    # --- 1. DADOS DE FINANCIAMENTOS (KANBAN) ---
    # Se for Admin, vê tudo. Se não, vê só os seus.
    if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
        qs_fichas = Ficha.objects.all()
    else:
        qs_fichas = Ficha.objects.filter(vendedor=user)

    # Contadores
    fichas_em_analise = qs_fichas.filter(status__in=['NOVA', 'EM_ANALISE']).count()
    fichas_aprovadas = qs_fichas.filter(status__in=['APROVADA', 'EM_ASSINATURA']).count()
    
    # --- 2. DADOS DE VENDAS (PRODUTOS) ---
    if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
        qs_vendas = VendaProduto.objects.filter(data_venda__month=mes_atual, data_venda__year=ano_atual)
    else:
        qs_vendas = VendaProduto.objects.filter(vendedor=user, data_venda__month=mes_atual, data_venda__year=ano_atual)

    vendas_count = qs_vendas.count()
    # Soma de comissão (se for vendedor, soma a comissão dele. Se admin, pode somar lucro ou comissão geral)
    minha_comissao = qs_vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or 0

    context = {
        'fichas_em_analise': fichas_em_analise,
        'fichas_aprovadas': fichas_aprovadas,
        'vendas_count': vendas_count,
        'minha_comissao': minha_comissao,
        'mes_atual_nome': hoje.strftime('%B'), # Nome do mês
    }
    
    return render(request, 'home.html', context)