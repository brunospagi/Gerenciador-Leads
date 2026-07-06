from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView, TemplateView
from django.contrib.auth.decorators import login_required
from crmspagi import views

admin.site.site_header = 'Spagi CRM — Administração'
admin.site.site_title = 'Spagi CRM Admin'
admin.site.index_title = 'Painel de Administração'

urlpatterns = [
    path('serviceworker.js', views.service_worker, name='service_worker'),
    path('favicon.ico', RedirectView.as_view(url='/static/images/logo-spagi-192x192.png', permanent=True)),
    path('admin/', admin.site.urls),
    path('painel-admin/', views.admin_dashboard, name='admin_dashboard'),
    path('painel-admin/dispensar-pendencias/', views.dispensar_pendencias_admin, name='dispensar_pendencias_admin'),
    path('painel-admin/backup/', views.gerar_backup_sistema, name='gerar_backup_sistema'),
    path('painel-admin/logs-auditoria/', views.logs_auditoria, name='logs_auditoria'),
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
    path('financeiro/', include('financeiro.urls')),
    path('ponto/', include('controle_ponto.urls')),
    path('erro/503/', views.error_503, name='erro_503'),
]

handler400 = 'crmspagi.views.error_400'
handler403 = 'crmspagi.views.error_403'
handler404 = 'crmspagi.views.error_404'
handler500 = 'crmspagi.views.error_500'
