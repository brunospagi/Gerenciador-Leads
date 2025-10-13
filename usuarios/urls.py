from django.urls import path
from .views import profile_view, CustomPasswordChangeView

urlpatterns = [
    path('perfil/', profile_view, name='profile'),
    path('perfil/trocar-senha/', CustomPasswordChangeView.as_view(), name='password_change'),
]