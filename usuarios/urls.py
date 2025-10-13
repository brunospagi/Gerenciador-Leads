from django.urls import path
from .views import (
    profile_view, CustomPasswordChangeView,
    UserListView, UserCreateView, UserUpdateView, UserDeleteView
)

urlpatterns = [
    # Rotas de perfil existentes
    path('perfil/', profile_view, name='profile'),
    path('perfil/trocar-senha/', CustomPasswordChangeView.as_view(), name='password_change'),

    # >> NOVAS ROTAS PARA GERENCIAMENTO DE USUÁRIOS <<
    path('usuarios/', UserListView.as_view(), name='user_list'),
    path('usuarios/novo/', UserCreateView.as_view(), name='user_create'),
    path('usuarios/<int:pk>/editar/', UserUpdateView.as_view(), name='user_update'),
    path('usuarios/<int:pk>/excluir/', UserDeleteView.as_view(), name='user_delete'),
]