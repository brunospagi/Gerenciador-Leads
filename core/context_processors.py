from .models import BannerSistema

def banner_context(request):
    # Pega o último banner marcado como ativo
    banner = BannerSistema.objects.filter(ativo=True).last()
    return {
        'banner_sistema': banner
    }