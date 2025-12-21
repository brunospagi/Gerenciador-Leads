from django.urls import path
from .views import (
    TVVideoView, 
    BannerListView, 
    BannerCreateView, 
    BannerUpdateView, 
    BannerDeleteView
)

urlpatterns = [
    path('tv-video/', TVVideoView.as_view(), name='tv_video_display'),
    path('banners/', BannerListView.as_view(), name='banner_list'),
    path('banners/novo/', BannerCreateView.as_view(), name='banner_create'),
    path('banners/<int:pk>/editar/', BannerUpdateView.as_view(), name='banner_update'),
    path('banners/<int:pk>/excluir/', BannerDeleteView.as_view(), name='banner_delete'),
]