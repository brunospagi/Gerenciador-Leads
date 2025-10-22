from django.urls import path
from .views import TVVideoView

urlpatterns = [
    path('tv-video/', TVVideoView.as_view(), name='tv_video_display'),
]