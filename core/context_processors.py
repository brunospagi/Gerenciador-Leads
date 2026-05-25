from django.conf import settings
from datetime import datetime
import subprocess

from .models import BannerSistema


def banner_context(request):
    # Pega o Ãºltimo banner marcado como ativo
    banner = BannerSistema.objects.filter(ativo=True).last()
    return {
        'banner_sistema': banner,
    }


def build_info_context(request):
    commit_sha = getattr(settings, 'APP_BUILD_SHA_SHORT', '')
    commit_dt = ''
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
    except Exception:
        pass

    return {
        'app_build_number': getattr(settings, 'APP_BUILD_NUMBER', '0'),
        'app_build_sha': commit_sha,
        'app_build_datetime': commit_dt,
    }
