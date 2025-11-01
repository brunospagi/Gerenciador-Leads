from django.urls import path
from .views import (
    ProcuracaoListView,
    ProcuracaoCreateView,
    ProcuracaoUpdateView,
    ProcuracaoDeleteView,
    gerar_procuracao_pdf,
    OutorgadoListView,
    OutorgadoCreateView,
    OutorgadoUpdateView,
    OutorgadoDeleteView,
)

urlpatterns = [
    # URLs de Procuração
    path('', ProcuracaoListView.as_view(), name='procuracao_list'),
    path('nova/', ProcuracaoCreateView.as_view(), name='procuracao_create'),
    path('<int:pk>/editar/', ProcuracaoUpdateView.as_view(), name='procuracao_update'),
    path('<int:pk>/excluir/', ProcuracaoDeleteView.as_view(), name='procuracao_delete'),
    path('<int:pk>/pdf/', gerar_procuracao_pdf, name='procuracao_pdf'),
    
    # URLs de Gerenciamento de Outorgados
    path('outorgados/', OutorgadoListView.as_view(), name='outorgado_list'),
    path('outorgados/novo/', OutorgadoCreateView.as_view(), name='outorgado_create'),
    path('outorgados/<int:pk>/editar/', OutorgadoUpdateView.as_view(), name='outorgado_update'),
    path('outorgados/<int:pk>/excluir/', OutorgadoDeleteView.as_view(), name='outorgado_delete'),
]