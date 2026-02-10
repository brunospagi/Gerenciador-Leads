from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_rh, name='rh_dashboard'),
    path('lancar-desconto/', views.lancar_desconto, name='lancar_desconto'),
    path('lancar-credito/', views.lancar_credito, name='lancar_credito'),
    path('folha/<int:pk>/', views.detalhe_folha, name='detalhe_folha'),
]