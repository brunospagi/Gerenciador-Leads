from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from .whatsapp import notificar_whatsapp_usuario


class NotificarWhatsappUsuarioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='vendedor_whatsapp', password='123456')
        self.user.dados_funcionais.telefone = '41999990000'
        self.user.dados_funcionais.save()

    @patch('notificacoes.whatsapp.enviar_webhook')
    def test_envia_quando_telefone_e_preferencia_ok(self, mock_enviar):
        notificar_whatsapp_usuario(self.user, 'Mensagem de teste')
        mock_enviar.assert_called_once()
        args, kwargs = mock_enviar.call_args
        self.assertEqual(args[1]['telefone'], '41999990000')
        self.assertEqual(args[1]['mensagem'], 'Mensagem de teste')

    @patch('notificacoes.whatsapp.enviar_webhook')
    def test_nao_envia_se_preferencia_desativada(self, mock_enviar):
        self.user.profile.notificacao_whatsapp = False
        self.user.profile.save()
        notificar_whatsapp_usuario(self.user, 'Mensagem de teste')
        mock_enviar.assert_not_called()

    @patch('notificacoes.whatsapp.enviar_webhook')
    def test_nao_envia_sem_telefone_cadastrado(self, mock_enviar):
        self.user.dados_funcionais.telefone = ''
        self.user.dados_funcionais.save()
        notificar_whatsapp_usuario(self.user, 'Mensagem de teste')
        mock_enviar.assert_not_called()
