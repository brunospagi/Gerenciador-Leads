from django.urls import path
from .views import dashboard_rh, lancar_desconto, detalhe_folha

urlpatterns = [
    path('', dashboard_rh, name='rh_dashboard'),
    path('desconto/novo/', lancar_desconto, name='rh_lancar_desconto'),
    path('folha/<int:pk>/', detalhe_folha, name='rh_detalhe_folha'),
]