from django.conf import settings

from .models import BannerSistema


def banner_context(request):
    # Pega o Ãºltimo banner marcado como ativo
    banner = BannerSistema.objects.filter(ativo=True).last()
    return {
        'banner_sistema': banner,
    }


def build_info_context(request):
    return {
        'app_build_number': getattr(settings, 'APP_BUILD_NUMBER', '0'),
        'app_build_sha': getattr(settings, 'APP_BUILD_SHA_SHORT', ''),
    }
