from django.contrib.auth.models import User
from django.test import TestCase

from usuarios.models import ModulePermission
from usuarios.permissions import has_module_access


class HasModuleAccessTests(TestCase):
    def test_respeita_permissao_explicita_do_modulo(self):
        user = User.objects.create_user(username='vendedor_padrao', password='123456')

        # Default do ModulePermission: modulo_financeiro=False, modulo_clientes=True.
        self.assertFalse(has_module_access(user, 'financeiro'))
        self.assertTrue(has_module_access(user, 'clientes'))

        user.module_permissions.modulo_financeiro = True
        user.module_permissions.save()
        self.assertTrue(has_module_access(user, 'financeiro'))

    def test_admin_revoga_modulo_e_permanece_revogado(self):
        user = User.objects.create_user(username='vendedor_revogado', password='123456')
        user.module_permissions.modulo_clientes = False
        user.module_permissions.save()

        self.assertFalse(has_module_access(user, 'clientes'))

    def test_registro_ausente_nao_libera_acesso_amplo(self):
        user = User.objects.create_user(username='vendedor_sem_registro', password='123456')
        ModulePermission.objects.filter(user=user).delete()
        # Rebusca o usuario para descartar o cache do reverse o2o (populado pelo
        # signal na criacao), simulando de fato um registro ausente no banco.
        user = User.objects.get(pk=user.pk)

        # Sem registro, deve autocurar com os defaults do model (nao liberar tudo por padrao).
        self.assertFalse(has_module_access(user, 'financeiro'))
        self.assertFalse(has_module_access(user, 'distribuicao'))
        self.assertTrue(has_module_access(user, 'clientes'))
        self.assertTrue(ModulePermission.objects.filter(user=user).exists())

    def test_modulo_desconhecido_nega_acesso(self):
        user = User.objects.create_user(username='vendedor_modulo_invalido', password='123456')
        self.assertFalse(has_module_access(user, 'modulo_que_nao_existe'))
