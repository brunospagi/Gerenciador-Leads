from django.urls import path
from .views import (
    profile_view, CustomPasswordChangeView,
    UserListView, UserCreateView, UserUpdateView, UserDeleteView,
    UserPasswordChangeView
)

urlpatterns = [
    path('perfil/', profile_view, name='profile'),
    path('perfil/trocar-senha/', CustomPasswordChangeView.as_view(), name='password_change'),

    path('usuarios/', UserListView.as_view(), name='user_list'),
    path('usuarios/novo/', UserCreateView.as_view(), name='user_create'),
    path('usuarios/<int:pk>/editar/', UserUpdateView.as_view(), name='user_update'),
    path('usuarios/<int:pk>/excluir/', UserDeleteView.as_view(), name='user_delete'),

    # >> NOVA ROTA PARA ALTERAR SENHA <<
    path('usuarios/<int:pk>/alterar-senha/', UserPasswordChangeView.as_view(), name='user_password_change'),
]