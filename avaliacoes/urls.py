from django.urls import path
from .views import (
    AvaliacaoListView,
    AvaliacaoCreateView,
    AvaliacaoDetailView,
    AvaliacaoUpdateView,
    AvaliacaoDeleteView,
    get_fipe_marcas,
    get_fipe_modelos,
    get_fipe_anos,
    gerador_anuncio_view, 
    bulk_gerador_anuncio_view, 
)

urlpatterns = [
    path('avaliacoes/', AvaliacaoListView.as_view(), name='avaliacao_list'),
    path('avaliacoes/nova/', AvaliacaoCreateView.as_view(), name='avaliacao_create'),
    path('avaliacoes/<int:pk>/', AvaliacaoDetailView.as_view(), name='avaliacao_detail'),
    path('avaliacoes/<int:pk>/editar/', AvaliacaoUpdateView.as_view(), name='avaliacao_update'),
    path('avaliacoes/<int:pk>/excluir/', AvaliacaoDeleteView.as_view(), name='avaliacao_delete'),

    # Rotas da API FIPE
    path('api/fipe/<str:tipo_veiculo>/marcas/', get_fipe_marcas, name='api_fipe_marcas'),
    path('api/fipe/<str:tipo_veiculo>/marcas/<int:marca_id>/modelos/', get_fipe_modelos, name='api_fipe_modelos'),
    path('api/fipe/<str:tipo_veiculo>/marcas/<int:marca_id>/modelos/<int:modelo_id>/anos/', get_fipe_anos, name='api_fipe_anos'),
    
    # Rotas do Gerador de Anúncios (NOVO)
    path('avaliacoes/gerar-anuncio/', gerador_anuncio_view, name='gerador_anuncio'),
    path('avaliacoes/gerar-anuncio/bulk/', bulk_gerador_anuncio_view, name='bulk_gerador_anuncio'),
]