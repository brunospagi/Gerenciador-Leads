# brunospagi/gerenciador-leads/Gerenciador-Leads-fecd02772f93afa4ca06347c8334383a86eb8295/avaliacoes/urls.py

from django.urls import path
from .views import (
    AvaliacaoListView,
    AvaliacaoCreateView,
    AvaliacaoDetailView,
    AvaliacaoUpdateView,
    # --- Importe as novas views da API ---
    get_fipe_marcas,
    get_fipe_modelos,
    get_fipe_anos,
)

urlpatterns = [
    path('avaliacoes/', AvaliacaoListView.as_view(), name='avaliacao_list'),
    path('avaliacoes/nova/', AvaliacaoCreateView.as_view(), name='avaliacao_create'),
    path('avaliacoes/<int:pk>/', AvaliacaoDetailView.as_view(), name='avaliacao_detail'),
    path('avaliacoes/<int:pk>/editar/', AvaliacaoUpdateView.as_view(), name='avaliacao_update'),

    # --- URLs da API FIPE ---
    path('api/fipe/marcas/', get_fipe_marcas, name='api_fipe_marcas'),
    path('api/fipe/marcas/<int:marca_id>/modelos/', get_fipe_modelos, name='api_fipe_modelos'),
    path('api/fipe/marcas/<int:marca_id>/modelos/<int:modelo_id>/anos/', get_fipe_anos, name='api_fipe_anos'),
]