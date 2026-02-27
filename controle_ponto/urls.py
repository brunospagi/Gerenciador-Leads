from django.urls import path
from . import views

app_name = 'controle_ponto'

urlpatterns = [
    path('', views.relogio_ponto, name='relogio'),
    path('mapa/', views.mapa_pontos, name='mapa_pontos'),
    path('relatorio/', views.relatorio_mensal, name='relatorio_mensal'),
]