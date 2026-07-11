from configuracoes.resolver import obter_matriz_permissoes


def module_access_context(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'module_access': {}, 'module_actions': {}}

    matriz = obter_matriz_permissoes(user)
    module_access = {slug: acoes['visualizar'] for slug, acoes in matriz.items()}
    return {'module_access': module_access, 'module_actions': matriz}
