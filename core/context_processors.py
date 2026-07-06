from django.conf import settings
from datetime import datetime
import subprocess
from django.utils import timezone
from django.utils import timezone

from .models import BannerSistema
from controle_ponto.models import RegistroPonto
from vendas_produtos.models import VendaProduto


def banner_context(request):
    # Pega o Ãºltimo banner marcado como ativo
    banner = BannerSistema.objects.filter(ativo=True).last()
    return {
        'banner_sistema': banner,
    }


def build_info_context(request):
    commit_sha = getattr(settings, 'APP_BUILD_SHA_SHORT', '') or ''
    commit_dt = ''
    build_number = str(getattr(settings, 'APP_BUILD_NUMBER', '0') or '0').strip()
    try:
        output = subprocess.check_output(
            ['git', 'log', '-1', '--format=%h|%cI'],
            cwd=str(settings.BASE_DIR),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
        ).strip()
        if output and '|' in output:
            git_sha, git_iso = output.split('|', 1)
            if git_sha:
                commit_sha = git_sha.strip()
            try:
                dt = datetime.fromisoformat(git_iso.strip().replace('Z', '+00:00'))
                commit_dt = dt.strftime('%d/%m/%Y %H:%M')
            except Exception:
                commit_dt = git_iso.strip()
        # Se APP_BUILD_NUMBER vier vazio/0, usa contagem de commits como fallback.
        if build_number in {'', '0'}:
            try:
                build_number = subprocess.check_output(
                    ['git', 'rev-list', '--count', 'HEAD'],
                    cwd=str(settings.BASE_DIR),
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.5,
                ).strip() or '0'
            except Exception:
                build_number = '0'
    except Exception:
        pass

    if build_number in {'', '0'}:
        env_build = (
            getattr(settings, 'APP_BUILD_SHA', '')
            or getattr(settings, 'APP_BUILD_SHA_SHORT', '')
            or getattr(settings, 'RENDER_GIT_COMMIT', '')
            or ''
        ).strip()
        if env_build:
            build_number = env_build[:8]

    if build_number in {'', '0'}:
        build_number = timezone.now().strftime('%Y%m%d%H%M')

    return {
        'app_build_number': build_number,
        'app_build_sha': commit_sha,
        'app_build_datetime': commit_dt,
    }


def ponto_pendencias_context(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    nivel = getattr(getattr(user, 'profile', None), 'nivel_acesso', '')
    is_admin = bool(user.is_superuser or nivel == 'ADMIN')
    if not is_admin:
        return {}

    if request.session.get('pendencias_admin_dispensadas'):
        return {}

    hoje = timezone.localdate()
    pendencias_qs = RegistroPonto.objects.filter(
        status_homologacao=RegistroPonto.StatusHomologacao.PENDENTE,
        data__year=hoje.year,
        data__month=hoje.month,
    )
    vendas_pendentes_qs = VendaProduto.objects.filter(
        status='PENDENTE',
        data_venda__year=hoje.year,
        data_venda__month=hoje.month,
    )
    return {
        'admin_tem_pendencias_ponto': pendencias_qs.exists(),
        'admin_total_pendencias_ponto': pendencias_qs.count(),
        'admin_tem_pendencias_vendas': vendas_pendentes_qs.exists(),
        'admin_total_pendencias_vendas': vendas_pendentes_qs.count(),
        'admin_pendencias_mes_ref': f'{hoje.month:02d}/{hoje.year}',
    }
