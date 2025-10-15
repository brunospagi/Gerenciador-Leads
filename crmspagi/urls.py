from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('contas/', include('django.contrib.auth.urls')),
    path('', include('clientes.urls')),
    path('', include('avaliacoes.urls')),
    path('', include('usuarios.urls')),
    path('', include('notificacoes.urls')),
    path(
        "serviceworker.js",
        TemplateView.as_view(
            template_name="serviceworker.js",
            content_type="application/javascript",
        ),
        name="serviceworker",
    ),
]