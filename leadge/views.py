from django.conf import settings
from django.contrib import messages
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .forms import BannerForm, TVProgramacaoItemForm, TVVideoForm
from .models import Banner, TVProgramacaoItem, TVVideo
from .services import get_tv_programacao_ativa, get_tv_programacao_ativa_lista


class TVVideoView(View):
    def get(self, request, *args, **kwargs):
        video_config, created = TVVideo.objects.get_or_create(
            defaults={
                'video_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&mute=1&loop=1&playlist=dQw4w9WgXcQ',
                'titulo': 'Video de exemplo (alterar no admin)',
            }
        )
        itens_ativos = get_tv_programacao_ativa_lista()
        item_ativo = itens_ativos[0] if itens_ativos else None
        playlist_mp4_urls = [
            item.video_mp4.url
            for item in itens_ativos
            if item.video_mp4 and getattr(item.video_mp4, 'url', None)
        ]
        playlist_mode = len(playlist_mp4_urls) >= 2
        video_ativo = item_ativo or video_config
        ticker_manual = (
            item_ativo.manual_news_ticker
            if item_ativo and item_ativo.manual_news_ticker
            else video_config.manual_news_ticker
        )

        context = {
            'video_config': video_config,
            'video_ativo': video_ativo,
            'item_ativo': item_ativo,
            'playlist_mode': playlist_mode,
            'playlist_mp4_urls': playlist_mp4_urls,
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
            'NEWS_API_KEY': video_config.newsdata_api_key,
            'MANUAL_NEWS': ticker_manual,
        }
        return render(request, 'leadge/tv_video.html', context)


class PortalView(TemplateView):
    template_name = 'portal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['banners'] = Banner.objects.filter(ativo=True).order_by('ordem', '-data_criacao')
        return context


class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or getattr(self.request.user.profile, 'nivel_acesso', '') == 'ADMIN'


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


class TVGestaoView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'leadge/tv_gestao.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config, _ = TVVideo.objects.get_or_create(
            defaults={
                'video_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&mute=1&loop=1&playlist=dQw4w9WgXcQ',
                'titulo': 'Video de exemplo (alterar no admin)',
            }
        )
        context['tv_config'] = config
        context['programacao'] = TVProgramacaoItem.objects.all().order_by('ordem', 'id')
        context['item_ativo'] = get_tv_programacao_ativa()
        return context


class TVConfigUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = TVVideo
    form_class = TVVideoForm
    template_name = 'leadge/tv_config_form.html'
    success_url = reverse_lazy('tv_gestao')

    def get_object(self, queryset=None):
        config, _ = TVVideo.objects.get_or_create(
            defaults={
                'video_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&mute=1&loop=1&playlist=dQw4w9WgXcQ',
                'titulo': 'Video de exemplo (alterar no admin)',
            }
        )
        return config

    def form_valid(self, form):
        messages.success(self.request, "Configurações globais da TV atualizadas com sucesso.")
        return super().form_valid(form)


class TVProgramacaoCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = TVProgramacaoItem
    form_class = TVProgramacaoItemForm
    template_name = 'leadge/tv_programacao_form.html'
    success_url = reverse_lazy('tv_gestao')

    def form_valid(self, form):
        messages.success(self.request, "Item da programação criado com sucesso.")
        return super().form_valid(form)


class TVProgramacaoUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = TVProgramacaoItem
    form_class = TVProgramacaoItemForm
    template_name = 'leadge/tv_programacao_form.html'
    success_url = reverse_lazy('tv_gestao')

    def form_valid(self, form):
        messages.success(self.request, "Item da programação atualizado com sucesso.")
        return super().form_valid(form)


class TVProgramacaoDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = TVProgramacaoItem
    template_name = 'leadge/tv_programacao_confirm_delete.html'
    success_url = reverse_lazy('tv_gestao')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Item da programação removido com sucesso.")
        return super().delete(request, *args, **kwargs)
