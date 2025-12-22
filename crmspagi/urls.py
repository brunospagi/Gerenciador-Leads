from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView # Certifique-se que isto está importado

urlpatterns = [
    path('admin/', admin.site.urls),
    path('contas/', include('django.contrib.auth.urls')),
    path('portal/', TemplateView.as_view(template_name='portal.html'), name='portal'),
    path('', include('leadge.urls')),
    path('', include('clientes.urls')), 
    path('', include('usuarios.urls')),
    path('', include('notificacoes.urls')),
    path('', include('avaliacoes.urls')),
    path('documentos/', include('documentos.urls')), 
    path('vendas/', include('vendas_produtos.urls')),
    path('autorizacoes/', include('autorizacoes.urls')),
]