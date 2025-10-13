from django.urls import path
from .views import lista_notificacoes, deletar_notificacao

urlpatterns = [
    path('notificacoes/', lista_notificacoes, name='lista_notificacoes'),
    path('notificacoes/<int:notificacao_id>/deletar/', deletar_notificacao, name='deletar_notificacao'),
]