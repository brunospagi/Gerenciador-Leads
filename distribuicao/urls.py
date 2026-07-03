from django.urls import path
from .views import (
    PainelDistribuicaoView,
    RelatorioDistribuicaoView,
    RedistribuirLeadView,
    verificar_duplicidade_whatsapp,
)

urlpatterns = [
    path('entrada/', PainelDistribuicaoView.as_view(), name='painel-distribuicao'),
    path('relatorio/', RelatorioDistribuicaoView.as_view(), name='relatorio-distribuicao'),
    path('redistribuir/<int:pk>/', RedistribuirLeadView.as_view(), name='redistribuir-lead'),
    path('verificar-duplicidade/', verificar_duplicidade_whatsapp, name='verificar-duplicidade-whatsapp'),
]