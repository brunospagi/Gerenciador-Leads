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
    'credenciais': 'modulo_credenciais',
}


def _get_profile(user):
    try:
        return user.profile
    except (AttributeError, ObjectDoesNotExist):
        return None


def _get_or_create_module_permissions(user):
    # Importado aqui para evitar import circular (models importa deste modulo indiretamente).
    from .models import ModulePermission

    try:
        return user.module_permissions
    except (AttributeError, ObjectDoesNotExist):
        # Usuario legitimo sem registro (ex.: criado antes da migracao 0007). Autocura
        # criando o registro com os defaults do model, em vez de liberar acesso amplo.
        permissao, _ = ModulePermission.objects.get_or_create(user=user)
        return permissao


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
        perms = _get_or_create_module_permissions(user)
    except (DatabaseError, OperationalError, ProgrammingError):
        # Falha de infra (ex.: migracao ainda nao aplicada) -> nega por seguranca
        # em vez de liberar acesso amplo aos modulos.
        return False

    return bool(getattr(perms, field_name, False))
