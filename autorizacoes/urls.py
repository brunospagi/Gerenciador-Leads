from django.urls import path
from .views import (
    AutorizacaoListView, 
    AutorizacaoCreateView, 
    AutorizacaoPrintView,
    aprovar_autorizacao,
    rejeitar_autorizacao
)

urlpatterns = [
    path('', AutorizacaoListView.as_view(), name='autorizacao_list'),
    path('nova/', AutorizacaoCreateView.as_view(), name='autorizacao_create'),
    path('<int:pk>/imprimir/', AutorizacaoPrintView.as_view(), name='autorizacao_print'),
    path('<int:pk>/aprovar/', aprovar_autorizacao, name='autorizacao_approve'),
    path('<int:pk>/rejeitar/', rejeitar_autorizacao, name='autorizacao_reject'),
]