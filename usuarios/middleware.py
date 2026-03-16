from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from .permissions import has_module_access


class ModulePermissionMiddleware:
    PATH_MODULE_MAP = [
        ('/clientes/', 'clientes'),
        ('/vendas/', 'vendas'),
        ('/financeiro/', 'financeiro'),
        ('/ponto/', 'ponto'),
        ('/financiamentos/', 'financiamentos'),
        ('/avaliacoes/', 'avaliacoes'),
        ('/api/fipe/', 'avaliacoes'),
        ('/documentos/', 'documentos'),
        ('/autorizacoes/', 'autorizacoes'),
        ('/distribuicao/', 'distribuicao'),
        ('/rh/', 'rh'),
        ('/funcionarios/', 'rh'),
        ('/usuarios/', 'usuarios_admin'),
        ('/administracao/dashboard/', 'relatorios'),
        ('/painel-admin/', 'relatorios'),
        ('/whatsapp/', 'whatsapp'),
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        path = request.path or ''

        if user and user.is_authenticated:
            for prefix, module_key in self.PATH_MODULE_MAP:
                if path.startswith(prefix):
                    if not has_module_access(user, module_key):
                        messages.error(request, "Acesso negado: voce nao possui permissao para este modulo.")
                        return redirect(reverse('portal'))
                    break

        return self.get_response(request)
