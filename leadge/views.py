from django.shortcuts import render
from django.views import View
from .models import TVVideo
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

# Usamos csrf_exempt para evitar problemas de CSRF em telas de exibição pública,
# mas mantenha o CSRF ativo nas demais partes do sistema.
@method_decorator(csrf_exempt, name='dispatch')
class TVVideoView(View):
    def get(self, request, *args, **kwargs):
        # Tenta obter a única instância do vídeo ou cria uma com defaults se não existir
        video_config, created = TVVideo.objects.get_or_create(
            defaults={
                'video_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&mute=1&loop=1&playlist=dQw4w9WgXcQ',
                'titulo': 'Vídeo de Exemplo (Alterar no Admin)'
            }
        )
        
        context = {
            'video_config': video_config,
        }
        return render(request, 'leadge/tv_video.html', context)