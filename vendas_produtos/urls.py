from django.urls import path
from .views import (
    VendaProdutoListView, 
    VendaProdutoCreateView, 
    VendaProdutoUpdateView, 
    VendaProdutoDeleteView,
    VendaProdutoPrintView,
    VendaProdutoRelatorioView,
    aprovar_venda_produto,
    rejeitar_venda_produto,
    toggle_fechamento_mes,
    ConfiguracaoComissaoView,
)

urlpatterns = [
    path('', VendaProdutoListView.as_view(), name='venda_produto_list'),
    path('novo/', VendaProdutoCreateView.as_view(), name='venda_produto_create'),
    path('<int:pk>/editar/', VendaProdutoUpdateView.as_view(), name='venda_produto_update'),
    path('<int:pk>/excluir/', VendaProdutoDeleteView.as_view(), name='venda_produto_delete'),
    path('<int:pk>/comprovante/', VendaProdutoPrintView.as_view(), name='venda_produto_print'),
    path('relatorio/', VendaProdutoRelatorioView.as_view(), name='venda_produto_relatorio'),
    path('<int:pk>/aprovar/', aprovar_venda_produto, name='venda_produto_approve'),
    path('<int:pk>/rejeitar/', rejeitar_venda_produto, name='venda_produto_reject'),
    path('fechamento/', toggle_fechamento_mes, name='venda_produto_fechamento'),
    path('configuracao/comissao/', ConfiguracaoComissaoView.as_view(), name='configuracao_comissao'),
]