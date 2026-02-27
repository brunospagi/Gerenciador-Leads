from django.urls import path
from . import views

app_name = 'controle_ponto'

urlpatterns = [
    path('', views.relogio_ponto, name='relogio'),
    path('mapa/', views.mapa_pontos, name='mapa_pontos'),
    path('relatorio/', views.relatorio_mensal, name='relatorio_mensal'),
    path('detalhe/<int:pk>/', views.detalhe_ponto, name='detalhe_ponto'),
    path('editar/<int:pk>/', views.RegistroPontoUpdateView.as_view(), name='editar_ponto'),
    path('excluir/<int:pk>/', views.RegistroPontoDeleteView.as_view(), name='excluir_ponto'),
]