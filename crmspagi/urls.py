from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('contas/', include('django.contrib.auth.urls')),
    path('', include('leadge.urls')),
    path('', include('clientes.urls')),
    path('', include('avaliacoes.urls')),
    path('', include('usuarios.urls')),
    path('', include('notificacoes.urls')),
    path('documentos/', include('documentos.urls')), 
]