from django.urls import path

from . import views

urlpatterns = [
    path('', views.veiculo_list, name='marketing_veiculo_list'),
    path('sincronizar/', views.iniciar_sincronizacao, name='marketing_iniciar_sincronizacao'),
    path('sincronizar/status/', views.status_sincronizacao, name='marketing_status_sincronizacao'),
    path('sincronizar/cancelar/', views.cancelar_sincronizacao, name='marketing_cancelar_sincronizacao'),
    path('provedor-imagem/', views.atualizar_provedor_imagem, name='marketing_atualizar_provedor_imagem'),
    path('lote/gerar/', views.iniciar_geracao_lote, name='marketing_iniciar_lote'),
    path('lote/contar/', views.contar_lote, name='marketing_contar_lote'),
    path('lote/<int:lote_id>/', views.revisao_lote, name='marketing_revisao_lote'),
    path('lote/<int:lote_id>/status/', views.status_lote, name='marketing_status_lote'),
    path('lote/<int:lote_id>/salvar-todas/', views.aprovar_lote, name='marketing_aprovar_lote'),
    path('lote/<int:lote_id>/enviar-webhook/', views.enviar_lote_webhook, name='marketing_enviar_lote_webhook'),
    path('post/<int:pk>/status/', views.post_atualizar_status, name='marketing_post_status'),
    path('post/<int:pk>/enviar-webhook/', views.enviar_post_webhook_view, name='marketing_post_enviar_webhook'),
    path('preview/<int:preview_id>/imagem/', views.preview_imagem, name='marketing_preview_imagem'),
    path('preview/<int:preview_id>/confirmar/', views.confirmar_preview, name='marketing_confirmar_preview'),
    path('preview/<int:preview_id>/descartar/', views.descartar_preview, name='marketing_descartar_preview'),
    path('layouts/', views.layout_list, name='marketing_layout_list'),
    path('layouts/novo/', views.layout_editor, name='marketing_layout_novo'),
    path('layouts/salvar/', views.layout_salvar, name='marketing_layout_salvar'),
    path('layouts/preview/', views.layout_preview, name='marketing_layout_preview'),
    path('layouts/<int:pk>/editar/', views.layout_editor, name='marketing_layout_editar'),
    path('layouts/<int:pk>/salvar/', views.layout_salvar, name='marketing_layout_atualizar'),
    path('layouts/<int:pk>/excluir/', views.layout_excluir, name='marketing_layout_excluir'),
    path('<int:pk>/', views.veiculo_detail, name='marketing_veiculo_detail'),
    path('<int:pk>/gerar-preview/', views.gerar_preview, name='marketing_gerar_preview'),
]
