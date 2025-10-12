from django.urls import path
from .views import (
    AvaliacaoListView,
    AvaliacaoCreateView,
    AvaliacaoDetailView,
    AvaliacaoUpdateView,
)

urlpatterns = [
    path('avaliacoes/', AvaliacaoListView.as_view(), name='avaliacao_list'),
    path('avaliacoes/nova/', AvaliacaoCreateView.as_view(), name='avaliacao_create'),
    path('avaliacoes/<int:pk>/', AvaliacaoDetailView.as_view(), name='avaliacao_detail'),
    path('avaliacoes/<int:pk>/editar/', AvaliacaoUpdateView.as_view(), name='avaliacao_update'),
]