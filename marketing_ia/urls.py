from django.urls import path

from . import views

urlpatterns = [
    path('', views.veiculo_list, name='marketing_veiculo_list'),
    path('sincronizar/', views.iniciar_sincronizacao, name='marketing_iniciar_sincronizacao'),
    path('sincronizar/status/', views.status_sincronizacao, name='marketing_status_sincronizacao'),
    path('lote/gerar/', views.iniciar_geracao_lote, name='marketing_iniciar_lote'),
    path('lote/<int:lote_id>/', views.revisao_lote, name='marketing_revisao_lote'),
    path('lote/<int:lote_id>/status/', views.status_lote, name='marketing_status_lote'),
    path('lote/<int:lote_id>/salvar-todas/', views.aprovar_lote, name='marketing_aprovar_lote'),
    path('post/<int:pk>/status/', views.post_atualizar_status, name='marketing_post_status'),
    path('post/<int:pk>/enviar-webhook/', views.enviar_post_webhook_view, name='marketing_post_enviar_webhook'),
    path('<int:pk>/', views.veiculo_detail, name='marketing_veiculo_detail'),
    path('<int:pk>/gerar-post/', views.gerar_post, name='marketing_gerar_post'),
]
