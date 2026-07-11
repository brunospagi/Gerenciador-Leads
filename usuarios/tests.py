from django.contrib.auth.models import User
from django.test import TestCase

from configuracoes.models import ModuloSistema, PermissaoModulo
from usuarios.permissions import has_module_access


class HasModuleAccessTests(TestCase):
    def setUp(self):
        # Os modulos de sistema ja vem semeados pela migration 0002 do app configuracoes.
        self.modulo_financeiro = ModuloSistema.objects.get(slug='financeiro')
        self.modulo_clientes = ModuloSistema.objects.get(slug='clientes')

    def test_sem_permissao_cadastrada_nega_acesso(self):
        user = User.objects.create_user(username='vendedor_padrao', password='123456')
        self.assertFalse(has_module_access(user, 'financeiro'))
        self.assertFalse(has_module_access(user, 'clientes'))

    def test_respeita_permissao_explicita_do_modulo(self):
        user = User.objects.create_user(username='vendedor_com_acesso', password='123456')
        PermissaoModulo.objects.create(user=user, modulo=self.modulo_financeiro, pode_visualizar=True)

        self.assertTrue(has_module_access(user, 'financeiro'))
        self.assertFalse(has_module_access(user, 'clientes'))

    def test_admin_tem_acesso_total_mesmo_sem_permissao_cadastrada(self):
        user = User.objects.create_user(username='admin_teste', password='123456')
        user.profile.nivel_acesso = 'ADMIN'
        user.profile.save()

        self.assertTrue(has_module_access(user, 'financeiro'))
        self.assertTrue(has_module_access(user, 'clientes'))

    def test_modulo_desconhecido_nega_acesso(self):
        user = User.objects.create_user(username='vendedor_modulo_invalido', password='123456')
        self.assertFalse(has_module_access(user, 'modulo_que_nao_existe'))
