from django.urls import path
from .views import (
    ClienteListView,
    ClienteDetailView,
    ClienteCreateView,
    ClienteUpdateView,
    adicionar_historico,
    ClienteAtrasadoListView,
    ClienteFinalizadoListView,
    offline_view,
    relatorio_dashboard,
    exportar_relatorio_pdf,
    ClienteDeleteView ,
    CalendarioView
)

urlpatterns = [
    path('', ClienteListView.as_view(), name='cliente_list'),
    path('calendario/', CalendarioView.as_view(), name='calendario'),
    path('relatorios/exportar/', exportar_relatorio_pdf, name='exportar_relatorio_pdf'),
    path('relatorios/', relatorio_dashboard, name='relatorios'),
    path('clientes/atrasados/', ClienteAtrasadoListView.as_view(), name='cliente_atrasados_list'),
    path('clientes/finalizados/', ClienteFinalizadoListView.as_view(), name='cliente_finalizados_list'),
    path('cliente/novo/', ClienteCreateView.as_view(), name='cliente_create'),
    path('cliente/<int:pk>/', ClienteDetailView.as_view(), name='cliente_detail'),
    path('cliente/<int:pk>/editar/', ClienteUpdateView.as_view(), name='cliente_update'),
    path('cliente/<int:pk>/excluir/', ClienteDeleteView.as_view(), name='cliente_delete'),
    path('cliente/<int:pk>/adicionar_historico/', adicionar_historico, name='adicionar_historico'),
    path('offline/', offline_view, name='offline'), # Adicione esta linha

]