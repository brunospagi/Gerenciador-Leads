from django.urls import path
from .views import PainelDistribuicaoView

urlpatterns = [
    path('entrada/', PainelDistribuicaoView.as_view(), name='painel-distribuicao'),
]