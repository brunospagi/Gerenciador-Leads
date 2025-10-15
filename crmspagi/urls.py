from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('contas/', include('django.contrib.auth.urls')),
    path('', include('clientes.urls')),
    path('', include('avaliacoes.urls')),
    path('', include('usuarios.urls')),
    path('', include('notificacoes.urls')),
    path('', include('pwa.urls')),
]