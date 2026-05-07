from django.urls import path
from .views import cadastrar_funcionario, editar_funcionario, lista_funcionarios

urlpatterns = [
    path('equipe/', lista_funcionarios, name='lista_funcionarios'), # Rota do Gerente
    path('novo/', cadastrar_funcionario, name='funcionario_create'),
    path('<int:pk>/editar/', editar_funcionario, name='funcionario_update'),
]
