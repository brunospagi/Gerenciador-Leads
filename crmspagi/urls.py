from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # URLs do app de autenticação (login, logout, etc.)
    path('contas/', include('django.contrib.auth.urls')),
    # URLs do seu app de clientes
    path('', include('clientes.urls')),
    # URLs do app de avaliações
    path('', include('avaliacoes.urls')),

]