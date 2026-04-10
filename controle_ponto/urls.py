from django.urls import path
from . import views

app_name = 'controle_ponto'

urlpatterns = [
    path('', views.relogio_ponto, name='relogio'),
    path('mapa/', views.mapa_pontos, name='mapa_pontos'),
    path('relatorio/', views.relatorio_mensal, name='relatorio_mensal'),
    path('ocorrencias/', views.ocorrencias_mensais, name='ocorrencias_mensais'),
    path('ocorrencias/<int:pk>/homologar/', views.homologar_ocorrencia, name='homologar_ocorrencia'),
    path('relatorio-entradas/', views.relatorio_entradas, name='relatorio_entradas'),
    path('detalhe/<int:pk>/', views.detalhe_ponto, name='detalhe_ponto'),
    path('editar/<int:pk>/', views.RegistroPontoUpdateView.as_view(), name='editar_ponto'),
    path('excluir/<int:pk>/', views.RegistroPontoDeleteView.as_view(), name='excluir_ponto'),
]
