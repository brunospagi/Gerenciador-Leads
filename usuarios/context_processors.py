from .permissions import has_module_access


def module_access_context(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'module_access': {}}

    module_access = {
        'clientes': has_module_access(user, 'clientes'),
        'vendas': has_module_access(user, 'vendas'),
        'financiamentos': has_module_access(user, 'financiamentos'),
        'ponto': has_module_access(user, 'ponto'),
        'avaliacoes': has_module_access(user, 'avaliacoes'),
        'financeiro': has_module_access(user, 'financeiro'),
        'distribuicao': has_module_access(user, 'distribuicao'),
        'rh': has_module_access(user, 'rh'),
        'documentos': has_module_access(user, 'documentos'),
        'autorizacoes': has_module_access(user, 'autorizacoes'),
        'relatorios': has_module_access(user, 'relatorios'),
        'usuarios_admin': has_module_access(user, 'usuarios_admin'),
        'credenciais': has_module_access(user, 'credenciais'),
        'whatsapp': has_module_access(user, 'whatsapp'),
    }
    return {'module_access': module_access}
