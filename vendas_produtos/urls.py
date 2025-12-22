from django.urls import path
from .views import (
    VendaProdutoListView, 
    VendaProdutoCreateView, 
    VendaProdutoUpdateView,
    VendaProdutoDeleteView,
    VendaProdutoPrintView,
    VendaProdutoRelatorioView,
    aprovar_venda_produto,
    rejeitar_venda_produto
)

urlpatterns = [
    path('', VendaProdutoListView.as_view(), name='venda_produto_list'),
    path('nova/', VendaProdutoCreateView.as_view(), name='venda_produto_create'),
    path('<int:pk>/editar/', VendaProdutoUpdateView.as_view(), name='venda_produto_update'),
    path('<int:pk>/excluir/', VendaProdutoDeleteView.as_view(), name='venda_produto_delete'),
    path('<int:pk>/comprovante/', VendaProdutoPrintView.as_view(), name='venda_produto_print'),
    path('<int:pk>/aprovar/', aprovar_venda_produto, name='venda_produto_approve'),
    path('<int:pk>/rejeitar/', rejeitar_venda_produto, name='venda_produto_reject'),
    path('relatorio/', VendaProdutoRelatorioView.as_view(), name='venda_produto_relatorio'),
]