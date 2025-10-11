from django.urls import path
from .views import (
    ClienteListView,
    ClienteDetailView,
    ClienteCreateView,
    ClienteUpdateView,
    adicionar_historico,
    ClienteAtrasadoListView,
    ClienteFinalizadoListView,
    relatorio_dashboard,
)

urlpatterns = [
    path('', ClienteListView.as_view(), name='cliente_list'),
    path('relatorios/', relatorio_dashboard, name='relatorios'),
    path('clientes/atrasados/', ClienteAtrasadoListView.as_view(), name='cliente_atrasados_list'),
    path('clientes/finalizados/', ClienteFinalizadoListView.as_view(), name='cliente_finalizados_list'),
    path('cliente/novo/', ClienteCreateView.as_view(), name='cliente_create'),
    path('cliente/<int:pk>/', ClienteDetailView.as_view(), name='cliente_detail'),
    path('cliente/<int:pk>/editar/', ClienteUpdateView.as_view(), name='cliente_update'),
    path('cliente/<int:pk>/adicionar_historico/', adicionar_historico, name='adicionar_historico'),
]