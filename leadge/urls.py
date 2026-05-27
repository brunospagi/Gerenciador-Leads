from django.urls import path
from .views import (
    TVVideoView, 
    TVGestaoView,
    TVConfigUpdateView,
    TVProgramacaoCreateView,
    TVProgramacaoUpdateView,
    TVProgramacaoDeleteView,
    BannerListView, 
    BannerCreateView, 
    BannerUpdateView, 
    BannerDeleteView
)

urlpatterns = [
    path('tv-video/', TVVideoView.as_view(), name='tv_video_display'),
    path('tv/gestao/', TVGestaoView.as_view(), name='tv_gestao'),
    path('tv/gestao/configuracao/', TVConfigUpdateView.as_view(), name='tv_config_update'),
    path('tv/gestao/programacao/nova/', TVProgramacaoCreateView.as_view(), name='tv_programacao_create'),
    path('tv/gestao/programacao/<int:pk>/editar/', TVProgramacaoUpdateView.as_view(), name='tv_programacao_update'),
    path('tv/gestao/programacao/<int:pk>/excluir/', TVProgramacaoDeleteView.as_view(), name='tv_programacao_delete'),
    path('banners/', BannerListView.as_view(), name='banner_list'),
    path('banners/novo/', BannerCreateView.as_view(), name='banner_create'),
    path('banners/<int:pk>/editar/', BannerUpdateView.as_view(), name='banner_update'),
    path('banners/<int:pk>/excluir/', BannerDeleteView.as_view(), name='banner_delete'),
]
