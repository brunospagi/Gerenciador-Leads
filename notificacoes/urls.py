from django.urls import path
from .views import deletar_todas_notificacoes, lista_notificacoes, deletar_notificacao

urlpatterns = [
    path('notificacoes/', lista_notificacoes, name='lista_notificacoes'),
    path('notificacoes/<int:notificacao_id>/deletar/', deletar_notificacao, name='deletar_notificacao'),
    path('notificacoes/deletar-todas/', deletar_todas_notificacoes, name='deletar_todas_notificacoes'),
]