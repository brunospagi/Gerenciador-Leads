def has_module_access(user, module_key):
    """Compatibilidade: 'ter acesso ao modulo' equivale a ter a acao 'visualizar'
    na matriz de permissoes (configuracoes.PermissaoModulo)."""
    from configuracoes.resolver import has_module_action
    return has_module_action(user, module_key, 'visualizar')
