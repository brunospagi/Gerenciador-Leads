from django.urls import path
from .views import (
    deletar_todas_notificacoes, 
    lista_notificacoes, 
    deletar_notificacao,
    save_webpush_subscription, 
    delete_webpush_subscription,
    get_vapid_public_key
)

urlpatterns = [
    path('notificacoes/', lista_notificacoes, name='lista_notificacoes'),
    path('notificacoes/<int:notificacao_id>/deletar/', deletar_notificacao, name='deletar_notificacao'),
    path('notificacoes/deletar-todas/', deletar_todas_notificacoes, name='deletar_todas_notificacoes'),    
    path('notificacoes/save-subscription/', save_webpush_subscription, name='save_webpush_subscription'),
    path('notificacoes/delete-subscription/', delete_webpush_subscription, name='delete_webpush_subscription'),
    path('notificacoes/vapid-public-key/', get_vapid_public_key, name='get_vapid_public_key'),
]