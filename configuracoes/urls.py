from django.urls import path

from .views import (
    ConfiguracaoIntegracoesUpdateView,
    ConfiguracoesHomeView,
    PermissaoModuloListView,
    PermissaoModuloMatrixView,
    WebhookIntegracaoCreateView,
    WebhookIntegracaoDeleteView,
    WebhookIntegracaoListView,
    WebhookIntegracaoUpdateView,
)

urlpatterns = [
    path('', ConfiguracoesHomeView.as_view(), name='configuracoes_home'),
    path('webhooks/', WebhookIntegracaoListView.as_view(), name='webhook_list'),
    path('webhooks/novo/', WebhookIntegracaoCreateView.as_view(), name='webhook_create'),
    path('webhooks/<int:pk>/editar/', WebhookIntegracaoUpdateView.as_view(), name='webhook_update'),
    path('webhooks/<int:pk>/excluir/', WebhookIntegracaoDeleteView.as_view(), name='webhook_delete'),
    path('integracoes/', ConfiguracaoIntegracoesUpdateView.as_view(), name='integracoes_form'),
    path('permissoes/', PermissaoModuloListView.as_view(), name='user_module_permissions'),
    path('permissoes/<int:pk>/', PermissaoModuloMatrixView.as_view(), name='user_module_permissions_update'),
]
