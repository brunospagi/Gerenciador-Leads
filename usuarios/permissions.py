from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError
from django.db.utils import OperationalError, ProgrammingError


MODULE_FIELD_MAP = {
    'clientes': 'modulo_clientes',
    'vendas': 'modulo_vendas',
    'financiamentos': 'modulo_financiamentos',
    'ponto': 'modulo_ponto',
    'avaliacoes': 'modulo_avaliacoes',
    'financeiro': 'modulo_financeiro',
    'distribuicao': 'modulo_distribuicao',
    'rh': 'modulo_rh',
    'documentos': 'modulo_documentos',
    'autorizacoes': 'modulo_autorizacoes',
    'relatorios': 'modulo_relatorios',
    'usuarios_admin': 'modulo_admin_usuarios',
}


def _get_profile(user):
    try:
        return user.profile
    except (AttributeError, ObjectDoesNotExist):
        return None


def _legacy_default_access(user, module_key):
    profile = _get_profile(user)
    nivel = getattr(profile, 'nivel_acesso', '')

    if module_key in {'clientes', 'vendas', 'financiamentos', 'ponto', 'avaliacoes'}:
        return True
    if module_key == 'financeiro':
        return bool(getattr(profile, 'pode_acessar_financeiro', False))
    if module_key == 'distribuicao':
        return nivel in {'ADMIN', 'GERENTE', 'DISTRIBUIDOR'} or bool(getattr(profile, 'pode_distribuir_leads', False))
    if module_key == 'rh':
        return nivel in {'ADMIN', 'GERENTE'}
    if module_key == 'relatorios':
        return nivel in {'ADMIN', 'GERENTE'}
    if module_key == 'usuarios_admin':
        return nivel == 'ADMIN'
    if module_key in {'documentos', 'autorizacoes'}:
        return True
    return False


def has_module_access(user, module_key):
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True

    profile = _get_profile(user)
    if getattr(profile, 'nivel_acesso', '') == 'ADMIN':
        return True

    field_name = MODULE_FIELD_MAP.get(module_key)
    if not field_name:
        return False

    try:
        perms = user.module_permissions
        return bool(getattr(perms, field_name, False))
    except (AttributeError, ObjectDoesNotExist, DatabaseError, OperationalError, ProgrammingError):
        return _legacy_default_access(user, module_key)
