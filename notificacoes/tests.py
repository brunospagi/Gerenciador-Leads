from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from configuracoes.models import ConfiguracaoIntegracoes

from .models import Notificacao
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


class CheckOverdueClientsCommandTests(TestCase):
    """Regressao: o job diario (check_overdue_clients) nao tinha nenhuma forma
    de ser desativado sem mexer no crontab/imagem — só o kill switch global
    ENABLE_CRON, que desliga todos os jobs de uma vez. Agora existe um toggle
    especifico (ConfiguracaoIntegracoes.notificar_leads_atrasados)."""

    def setUp(self):
        self.vendedor = User.objects.create_user(username='vendedor_atrasado', password='123456')
        self.admin = User.objects.create_user(username='admin_atrasado', password='123456', is_staff=True)
        self.admin.profile.nivel_acesso = self.admin.profile.NivelAcesso.ADMIN
        self.admin.profile.save()

        self.cliente = Cliente.objects.create(
            vendedor=self.vendedor,
            nome_cliente='Cliente Atrasado',
            whatsapp='41999990000',
            tipo_contato=Cliente.TipoContato.MENSAGEM,
            proximo_passo=Cliente.ProximoPasso.MENSAGEM,
        )
        # save() sobrescreve data_proximo_contato pra +5 dias na criação —
        # forçar a data pro passado direto no banco, sem passar por save().
        Cliente.objects.filter(pk=self.cliente.pk).update(
            data_proximo_contato=timezone.now() - timedelta(days=1),
        )

    def test_notifica_vendedor_e_admin_quando_ativado(self):
        call_command('check_overdue_clients')
        self.assertTrue(
            Notificacao.objects.filter(usuario=self.vendedor, mensagem__icontains='Contato Atrasado').exists()
        )
        self.assertTrue(
            Notificacao.objects.filter(usuario=self.admin, mensagem__icontains='Alerta geral').exists()
        )

    def test_nao_notifica_quando_desativado_no_painel(self):
        config = ConfiguracaoIntegracoes.get_solo()
        config.notificar_leads_atrasados = False
        config.save(update_fields=['notificar_leads_atrasados'])

        call_command('check_overdue_clients')

        self.assertFalse(
            Notificacao.objects.filter(usuario=self.vendedor, mensagem__icontains='Contato Atrasado').exists()
        )
        self.assertFalse(
            Notificacao.objects.filter(usuario=self.admin, mensagem__icontains='Alerta geral').exists()
        )

    def test_ativado_por_padrao(self):
        self.assertTrue(ConfiguracaoIntegracoes.get_solo().notificar_leads_atrasados)
