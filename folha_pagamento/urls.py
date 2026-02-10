from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard_rh, name='rh_dashboard'),
    
    # Lançamentos
    path('desconto/novo/', views.lancar_desconto, name='rh_lancar_desconto'),
    path('credito/novo/', views.lancar_credito, name='rh_lancar_credito'), # Adicionado
    
    # Detalhes
    path('folha/<int:pk>/', views.detalhe_folha, name='rh_detalhe_folha'),
]