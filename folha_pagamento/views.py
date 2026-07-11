from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
import hashlib
import json
import calendar
from datetime import datetime, date
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.views.decorators.http import require_POST
from django.urls import reverse
from configuracoes.access import require_module_action
from .models import FolhaPagamento, Desconto, ParcelaDesconto, Credito, ParcelaCredito
from funcionarios.models import Funcionario
from vendas_produtos.models import VendaProduto
from .forms import LancarDescontoForm, LancarCreditoForm, ProcessarFolhaForm

def is_admin_financeiro(user):
    # Retorna True se for Superuser ou se tiver perfil ADMIN
    if user.is_superuser:
        return True
    return getattr(getattr(user, 'profile', None), 'nivel_acesso', '') == 'ADMIN'

def _recalcular_folhas_abertas_por_parcelas(funcionario, parcelas):
    referencias = set((p.mes_referencia, p.ano_referencia) for p in parcelas)
    _recalcular_folhas_abertas_por_referencias(funcionario, referencias)

def _recalcular_folhas_abertas_por_referencias(funcionario, referencias):
    for mes, ano in referencias:
        folha, _ = FolhaPagamento.objects.get_or_create(
            funcionario=funcionario,
            mes=mes,
            ano=ano,
            defaults={'salario_base': funcionario.salario_base},
        )
        if not folha.fechada:
            folha.calcular_folha()

@require_module_action('rh', 'editar')
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

    # Sempre garante a existência das folhas na referência selecionada.
    for func in funcionarios:
        folha, _ = FolhaPagamento.objects.get_or_create(
            funcionario=func,
            mes=mes,
            ano=ano,
            defaults={'salario_base': func.salario_base},
        )
        if request.method != 'POST' and not folha.fechada:
            folha.calcular_folha()

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

            elif acao == 'atualizar_mes':
                count = 0
                for func in funcionarios:
                    folha, _ = FolhaPagamento.objects.get_or_create(
                        funcionario=func, mes=mes, ano=ano,
                        defaults={'salario_base': func.salario_base}
                    )
                    folha.calcular_folha(force=True)
                    count += 1
                messages.success(
                    request,
                    f"{count} folhas recalculadas para {mes:02d}/{ano} "
                    "(incluindo fechadas, sem alterar status)."
                )
            else:
                messages.info(request, "Ação inválida.")

            return redirect(f"{reverse('rh_dashboard')}?mes={mes}&ano={ano}")
    else:
        form_folha = ProcessarFolhaForm(initial={'mes': mes, 'ano': ano})

    referencia_atual = date(ano, mes, 1)
    mes_anterior = referencia_atual - relativedelta(months=1)
    mes_proximo = referencia_atual + relativedelta(months=1)

    return render(request, 'folha_pagamento/dashboard_rh.html', {
        'funcionarios': funcionarios,
        'folhas': folhas_mes,
        'form_folha': form_folha,
        'mes_referencia': mes,
        'ano_referencia': ano,
        'total_folhas': folhas_mes.count(),
        'total_fechadas': folhas_mes.filter(fechada=True).count(),
        'total_pagas': folhas_mes.filter(pago=True).count(),
        'nav_anterior_mes': mes_anterior.month,
        'nav_anterior_ano': mes_anterior.year,
        'nav_proximo_mes': mes_proximo.month,
        'nav_proximo_ano': mes_proximo.year,
    })

@require_module_action('rh', 'criar')
@user_passes_test(is_admin_financeiro)
def lancar_desconto(request):
    if request.method == 'POST':
        form = LancarDescontoForm(request.POST)
        if form.is_valid():
            desconto = form.save()
            _recalcular_folhas_abertas_por_parcelas(desconto.funcionario, desconto.parcelas.all())
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

@require_module_action('rh', 'editar')
@user_passes_test(is_admin_financeiro)
def editar_desconto(request, pk):
    desconto = get_object_or_404(
        Desconto.objects.select_related('funcionario', 'funcionario__user'),
        pk=pk
    )

    if desconto.parcelas.filter(processada_na_folha=True).exists():
        messages.error(
            request,
            "Este desconto/vale ja foi processado em folha fechada e nao pode ser alterado."
        )
        return redirect('rh_lista_lancamentos')

    parcelas_anteriores = list(desconto.parcelas.all())
    referencias_anteriores = {
        (p.mes_referencia, p.ano_referencia) for p in parcelas_anteriores
    }

    if request.method == 'POST':
        form = LancarDescontoForm(request.POST, instance=desconto)
        if form.is_valid():
            with transaction.atomic():
                desconto = form.save()
                desconto.parcelas.all().delete()
                desconto.gerar_parcelas()
                referencias_novas = {
                    (p.mes_referencia, p.ano_referencia)
                    for p in desconto.parcelas.all()
                }

            referencias = referencias_anteriores | referencias_novas
            _recalcular_folhas_abertas_por_referencias(desconto.funcionario, referencias)
            messages.success(request, "Desconto/vale atualizado com sucesso.")
            return redirect('rh_lista_lancamentos')
    else:
        form = LancarDescontoForm(instance=desconto)

    return render(request, 'folha_pagamento/form_desconto.html', {
        'form': form,
        'titulo': 'Editar Debito/Desconto',
        'cor_card': 'warning',
        'icone': 'fa-edit',
        'btn_label': 'Salvar Alteracao',
        'cancel_url': reverse('rh_lista_lancamentos'),
    })

@require_module_action('rh', 'excluir')
@user_passes_test(is_admin_financeiro)
def excluir_desconto(request, pk):
    desconto = get_object_or_404(
        Desconto.objects.select_related('funcionario', 'funcionario__user'),
        pk=pk
    )

    bloqueado = desconto.parcelas.filter(processada_na_folha=True).exists()

    if request.method == 'POST':
        if bloqueado:
            messages.error(
                request,
                "Este desconto/vale ja foi processado em folha fechada e nao pode ser excluido."
            )
            return redirect('rh_lista_lancamentos')

        parcelas = list(desconto.parcelas.all())
        referencias = {(p.mes_referencia, p.ano_referencia) for p in parcelas}
        funcionario = desconto.funcionario

        with transaction.atomic():
            desconto.delete()

        _recalcular_folhas_abertas_por_referencias(funcionario, referencias)
        messages.success(request, "Desconto/vale excluido com sucesso.")
        return redirect('rh_lista_lancamentos')

    return render(request, 'folha_pagamento/confirmar_delete_desconto.html', {
        'desconto': desconto,
        'bloqueado': bloqueado,
    })

@require_module_action('rh', 'criar')
@user_passes_test(is_admin_financeiro)
def lancar_credito(request):
    if request.method == 'POST':
        form = LancarCreditoForm(request.POST)
        if form.is_valid():
            credito = form.save()
            _recalcular_folhas_abertas_por_parcelas(credito.funcionario, credito.parcelas.all())
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

@require_module_action('rh', 'visualizar')
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

    vendas_base_equipe = VendaProduto.objects.none()
    if is_gerente:
        # Comissão de gerência: exclui vendas em nome de GERENTE/ADMIN/superusuário.
        vendas_base_equipe = (
            VendaProduto.objects.filter(
                data_venda__range=[data_inicio, data_fim],
                status='APROVADO',
                tipo_produto__in=['VENDA_VEICULO', 'VENDA_MOTO'],
            )
            .exclude(vendedor=folha.funcionario.user)
            .exclude(vendedor__is_superuser=True)
            .exclude(vendedor__profile__nivel_acesso__in=['ADMIN', 'GERENTE'])
        )
        qtd_carros_equipe = vendas_base_equipe.filter(tipo_produto='VENDA_VEICULO').count()
        qtd_motos_equipe = vendas_base_equipe.filter(tipo_produto='VENDA_MOTO').count()

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

    # Totalizadores para exibição (sempre baseados na mesma grade exibida no holerite)
    total_vencimentos = Decimal('0.00')
    total_descontos = Decimal('0.00')
    for item in itens_holerite:
        total_vencimentos += Decimal(item.get('vencimentos') or 0)
        total_descontos += Decimal(item.get('descontos') or 0)
    salario_liquido_exibicao = total_vencimentos - total_descontos

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
    total_conferencia_gerencia = Decimal('0.00')
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
            'veiculo': f"{(venda.marca_veiculo or '').strip()} {(venda.modelo_veiculo or '').strip()}".strip() or '-',
            'placa': venda.placa or '-',
            'papel': meu_papel,
            'minha_comissao': minha_comissao or Decimal('0.00'),
            'comissao_outro': comissao_outro or Decimal('0.00'),
            'outro_nome': (outro_usuario.get_full_name() or outro_usuario.username) if outro_usuario else '-',
            'is_gerencia': False,
        })
        total_conferencia_minha += minha_comissao or Decimal('0.00')
        total_conferencia_outro += comissao_outro or Decimal('0.00')

    # Detalhamento da comissão de gerência por venda da equipe.
    if is_gerente:
        for venda in vendas_base_equipe.select_related('vendedor').order_by('data_venda', 'id'):
            valor_comissao_gerencia = Decimal('150.00') if venda.tipo_produto == 'VENDA_VEICULO' else Decimal('80.00')
            conferencias_comissoes.append({
                'data_venda': venda.data_venda,
                'cliente_nome': venda.cliente_nome,
                'tipo_produto': venda.get_tipo_produto_display(),
                'veiculo': f"{(venda.marca_veiculo or '').strip()} {(venda.modelo_veiculo or '').strip()}".strip() or '-',
                'placa': venda.placa or '-',
                'papel': 'Gerência (Equipe)',
                'minha_comissao': valor_comissao_gerencia,
                'comissao_outro': Decimal('0.00'),
                'outro_nome': venda.vendedor.get_full_name() or venda.vendedor.username,
                'is_gerencia': True,
            })
            total_conferencia_minha += valor_comissao_gerencia
            total_conferencia_gerencia += valor_comissao_gerencia

    conferencias_comissoes.sort(
        key=lambda item: (item['data_venda'], item['cliente_nome'] or '', item['papel'])
    )

    hash_payload = {
        'folha_id': folha.id,
        'funcionario_id': folha.funcionario_id,
        'mes': folha.mes,
        'ano': folha.ano,
        'fechada': folha.fechada,
        'pago': folha.pago,
        'total_vencimentos': str(total_vencimentos),
        'total_descontos': str(total_descontos),
        'salario_liquido': str(salario_liquido_exibicao),
        'itens': [
            {
                'codigo': item.get('codigo'),
                'descricao': item.get('descricao'),
                'referencia': item.get('referencia'),
                'vencimentos': str(item.get('vencimentos') or Decimal('0.00')),
                'descontos': str(item.get('descontos') or Decimal('0.00')),
            }
            for item in itens_holerite
        ],
        'conferencias': [
            {
                'data_venda': conf['data_venda'].isoformat() if conf.get('data_venda') else None,
                'cliente_nome': conf.get('cliente_nome'),
                'tipo_produto': conf.get('tipo_produto'),
                'veiculo': conf.get('veiculo'),
                'placa': conf.get('placa'),
                'papel': conf.get('papel'),
                'minha_comissao': str(conf.get('minha_comissao') or Decimal('0.00')),
                'comissao_outro': str(conf.get('comissao_outro') or Decimal('0.00')),
                'outro_nome': conf.get('outro_nome'),
                'is_gerencia': bool(conf.get('is_gerencia')),
            }
            for conf in conferencias_comissoes
        ],
    }
    holerite_hash = hashlib.sha256(
        json.dumps(hash_payload, sort_keys=True, ensure_ascii=True).encode('utf-8')
    ).hexdigest().upper()

    return render(request, 'folha_pagamento/detalhe_folha.html', {
        'folha': folha,
        'itens': itens_holerite,
        'total_vencimentos': total_vencimentos,
        'total_descontos': total_descontos,
        'salario_liquido_exibicao': salario_liquido_exibicao,
        'conferencias_comissoes': conferencias_comissoes,
        'total_conferencia_minha': total_conferencia_minha,
        'total_conferencia_outro': total_conferencia_outro,
        'total_conferencia_gerencia': total_conferencia_gerencia,
        'holerite_hash': holerite_hash,
    })

@require_module_action('rh', 'editar')
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
