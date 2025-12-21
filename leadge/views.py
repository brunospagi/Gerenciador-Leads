from django.shortcuts import render, redirect
from django.views import View
from .models import Banner, TVVideo
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings 
from django.views.generic import TemplateView
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Banner, TVVideo
from .forms import BannerForm

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
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY, 
            'NEWS_API_KEY': video_config.newsdata_api_key,
            'MANUAL_NEWS': video_config.manual_news_ticker,
        }
        return render(request, 'leadge/tv_video.html', context)

class PortalView(TemplateView):
    template_name = 'portal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['banners'] = Banner.objects.filter(ativo=True).order_by('ordem', '-data_criacao')
        return context
    
# Mixin para garantir que só ADMIN acesse
class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or getattr(self.request.user.profile, 'nivel_acesso', '') == 'ADMIN'

# --- VIEWS DE BANNER ---

class BannerListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Banner
    template_name = 'leadge/banner_list.html'
    context_object_name = 'banners'

class BannerCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Banner
    form_class = BannerForm
    template_name = 'leadge/banner_form.html'
    success_url = reverse_lazy('banner_list')

class BannerUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Banner
    form_class = BannerForm
    template_name = 'leadge/banner_form.html'
    success_url = reverse_lazy('banner_list')

class BannerDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Banner
    template_name = 'leadge/banner_confirm_delete.html'
    success_url = reverse_lazy('banner_list')