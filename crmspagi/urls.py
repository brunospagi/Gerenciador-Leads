from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('admin/', admin.site.urls),
    path('contas/', include('django.contrib.auth.urls')),
    path('', login_required(TemplateView.as_view(template_name='portal.html')), name='portal'),    path('', include('leadge.urls')),
    path('clientes/', include('clientes.urls')), 
    path('', include('usuarios.urls')),
    path('', include('notificacoes.urls')),
    path('', include('avaliacoes.urls')),
    path('documentos/', include('documentos.urls')), 
    path('vendas/', include('vendas_produtos.urls')),
    path('autorizacoes/', include('autorizacoes.urls')),
    path('financiamentos/', include('financiamentos.urls')),
    path('oidc/', include('mozilla_django_oidc.urls')),
    path('distribuicao/', include('distribuicao.urls')),
    path('acessos/', include('credenciais.urls')),
    path('rh/', include('folha_pagamento.urls')),
    path('funcionarios/', include('funcionarios.urls')),
    
]