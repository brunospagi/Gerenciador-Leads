from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Q
from django.http import FileResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model

# Importe os modelos dos seus aplicativos
from vendas_produtos.models import VendaProduto
from financeiro.models import TransacaoFinanceira
from controle_ponto.models import RegistroPonto
from core.backup_utils import create_system_backup
from core.models import AuditLog


def _is_admin_or_gerente(user):
    profile = getattr(user, 'profile', None)
    nivel = getattr(profile, 'nivel_acesso', '')
    return user.is_superuser or nivel in ['ADMIN', 'GERENTE']


def _is_admin_only(user):
    profile = getattr(user, 'profile', None)
    nivel = getattr(profile, 'nivel_acesso', '')
    return user.is_superuser or nivel == 'ADMIN'

@login_required
def admin_dashboard(request):
    # Trava de Segurança: Apenas Admin ou Gerente
    if not _is_admin_or_gerente(request.user):
        messages.error(request, "Acesso negado. Esta área é restrita à diretoria.")
        return redirect('portal') # Redireciona para o portal inicial comum

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


@login_required
@require_POST
def gerar_backup_sistema(request):
    if not _is_admin_or_gerente(request.user):
        messages.error(request, "Acesso negado para gerar backup.")
        return redirect('portal')

    try:
        backup_path = create_system_backup()
    except Exception as exc:
        messages.error(request, f"Falha ao gerar backup: {exc}")
        return redirect('admin_dashboard')

    response = FileResponse(open(backup_path, "rb"), as_attachment=True)
    response["Content-Type"] = "application/zip"
    response["Content-Disposition"] = f'attachment; filename="{backup_path.name}"'
    return response


@login_required
def logs_auditoria(request):
    if not _is_admin_only(request.user):
        messages.error(request, "Acesso negado. Apenas administradores podem consultar auditoria.")
        return redirect('portal')

    qs = AuditLog.objects.select_related("user").all()

    busca = (request.GET.get("q") or "").strip()
    if busca:
        qs = qs.filter(
            Q(module__icontains=busca)
            | Q(action__icontains=busca)
            | Q(path__icontains=busca)
            | Q(username_snapshot__icontains=busca)
            | Q(object_repr__icontains=busca)
        )

    user_id = (request.GET.get("user_id") or "").strip()
    if user_id.isdigit():
        qs = qs.filter(user_id=int(user_id))

    module_name = (request.GET.get("module") or "").strip()
    if module_name:
        qs = qs.filter(module=module_name)

    method = (request.GET.get("method") or "").strip().upper()
    if method:
        qs = qs.filter(method=method)

    severity = (request.GET.get("severity") or "").strip().upper()
    if severity in dict(AuditLog.SEVERITY_CHOICES):
        qs = qs.filter(severity=severity)

    success = (request.GET.get("success") or "").strip().lower()
    if success == "1":
        qs = qs.filter(success=True)
    elif success == "0":
        qs = qs.filter(success=False)

    data_inicio = (request.GET.get("data_inicio") or "").strip()
    if data_inicio:
        qs = qs.filter(created_at__date__gte=data_inicio)

    data_fim = (request.GET.get("data_fim") or "").strip()
    if data_fim:
        qs = qs.filter(created_at__date__lte=data_fim)

    paginator = Paginator(qs.order_by("-created_at"), 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_params = request.GET.copy()
    query_params.pop("page", None)
    querystring_base = query_params.urlencode()

    user_ids = (
        AuditLog.objects.exclude(user_id__isnull=True)
        .order_by("user_id")
        .values_list("user_id", flat=True)
        .distinct()[:300]
    )
    User = get_user_model()
    usuarios_filtro = User.objects.filter(id__in=list(user_ids)).order_by("first_name", "username")
    modulos_filtro = AuditLog.objects.values_list("module", flat=True).distinct().order_by("module")

    context = {
        "page_obj": page_obj,
        "usuarios_filtro": usuarios_filtro,
        "modulos_filtro": modulos_filtro,
        "filtro_q": busca,
        "filtro_user_id": user_id,
        "filtro_module": module_name,
        "filtro_method": method,
        "filtro_severity": severity,
        "filtro_success": success,
        "filtro_data_inicio": data_inicio,
        "filtro_data_fim": data_fim,
        "querystring_base": querystring_base,
    }
    return render(request, "logs_auditoria.html", context)


def _render_error_page(request, status_code, title, message):
    return render(
        request,
        'error_generic.html',
        {
            'status_code': status_code,
            'error_title': title,
            'error_message': message,
        },
        status=status_code,
    )


def error_400(request, exception=None):
    return _render_error_page(
        request,
        400,
        'Solicitacao invalida',
        'Nao foi possivel processar esta solicitacao. Tente novamente.',
    )


def error_403(request, exception=None):
    return _render_error_page(
        request,
        403,
        'Acesso negado',
        'Voce nao possui permissao para acessar este recurso.',
    )


def error_404(request, exception=None):
    return _render_error_page(
        request,
        404,
        'Pagina nao encontrada',
        'A pagina solicitada nao existe ou foi movida.',
    )


def error_500(request):
    return _render_error_page(
        request,
        500,
        'Erro interno do sistema',
        'Ocorreu uma instabilidade. Nossa equipe tecnica ja pode atuar neste caso.',
    )


def error_503(request, exception=None):
    return _render_error_page(
        request,
        503,
        'Servico temporariamente indisponivel',
        'O sistema esta passando por manutencao ou instabilidade momentanea. Tente novamente em instantes.',
    )


def csrf_failure(request, reason=''):
    return _render_error_page(
        request,
        403,
        'Sessao expirada ou validacao de seguranca',
        'Sua sessao expirou ou houve falha de validacao. Atualize a pagina e tente novamente.',
    )
