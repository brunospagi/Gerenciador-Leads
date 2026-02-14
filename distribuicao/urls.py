from django.urls import path
from .views import PainelDistribuicaoView, RelatorioDistribuicaoView

urlpatterns = [
    path('entrada/', PainelDistribuicaoView.as_view(), name='painel-distribuicao'),
    path('relatorio/', RelatorioDistribuicaoView.as_view(), name='relatorio-distribuicao'),
]