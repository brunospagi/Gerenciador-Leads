from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import ConfiguracaoIntegracoes, ModuloSistema, PermissaoModulo, WebhookIntegracao
from .resolver import enviar_webhook, has_module_action, obter_integracao, obter_webhook_url


class ObterWebhookUrlTests(TestCase):
    # DISTRIBUICAO_LEADS ja vem semeado (url='', ativo=True) pela migration 0002 —
    # usamos um slug proprio pra nao colidir com o registro nativo.
    @override_settings(N8N_WEBHOOK_URL='https://env.exemplo/webhook')
    def test_sem_registro_no_painel_cai_no_fallback_de_env(self):
        self.assertEqual(obter_webhook_url('DISTRIBUICAO_LEADS'), 'https://env.exemplo/webhook')

    def test_registro_com_url_no_painel_tem_prioridade(self):
        WebhookIntegracao.objects.create(
            nome='Webhook Teste', slug='WEBHOOK_TESTE', url='https://painel.exemplo/webhook', ativo=True,
        )
        self.assertEqual(obter_webhook_url('WEBHOOK_TESTE'), 'https://painel.exemplo/webhook')

    def test_registro_inativo_bloqueia_mesmo_com_env_configurada(self):
        WebhookIntegracao.objects.create(nome='Webhook Teste', slug='WEBHOOK_TESTE', url='', ativo=False)
        with override_settings(N8N_WEBHOOK_URL='https://env.exemplo/webhook'):
            self.assertIsNone(obter_webhook_url('WEBHOOK_TESTE'))

    def test_registro_ativo_sem_url_cai_no_fallback_de_env(self):
        # DISTRIBUICAO_LEADS ja vem semeado com url='' ativo=True; tem fallback mapeado.
        with override_settings(N8N_WEBHOOK_URL='https://env.exemplo/webhook'):
            self.assertEqual(obter_webhook_url('DISTRIBUICAO_LEADS'), 'https://env.exemplo/webhook')

    def test_slug_sem_fallback_mapeado_retorna_none(self):
        self.assertIsNone(obter_webhook_url('SLUG_QUE_NAO_EXISTE'))


class EnviarWebhookTests(TestCase):
    @patch('requests.post')
    def test_nao_chama_requests_se_sem_url(self, mock_post):
        enviar_webhook('SERVICO_SEM_URL', {'a': 1})
        mock_post.assert_not_called()

    @patch('requests.post')
    def test_chama_requests_quando_ha_url(self, mock_post):
        WebhookIntegracao.objects.create(nome='Teste', slug='TESTE', url='https://painel.exemplo/webhook', ativo=True)
        enviar_webhook('TESTE', {'a': 1}, timeout=5)
        mock_post.assert_called_once_with('https://painel.exemplo/webhook', json={'a': 1}, timeout=5)

    @patch('requests.post', side_effect=Exception('falhou'))
    def test_excecao_de_rede_nao_propaga(self, mock_post):
        WebhookIntegracao.objects.create(nome='Teste', slug='TESTE', url='https://painel.exemplo/webhook', ativo=True)
        enviar_webhook('TESTE', {'a': 1})  # nao deve lancar


class ObterIntegracaoTests(TestCase):
    @override_settings(EVO_CRM_API_TOKEN='token-do-env')
    def test_sem_valor_no_painel_cai_no_fallback_de_env(self):
        self.assertEqual(obter_integracao('evo_crm_api_token'), 'token-do-env')

    @override_settings(EVO_CRM_API_TOKEN='token-do-env')
    def test_valor_no_painel_tem_prioridade(self):
        config = ConfiguracaoIntegracoes.get_solo()
        config.evo_crm_api_token = 'token-do-painel'
        config.save()
        self.assertEqual(obter_integracao('evo_crm_api_token'), 'token-do-painel')


class HasModuleActionTests(TestCase):
    def setUp(self):
        self.modulo = ModuloSistema.objects.get(slug='financeiro')

    def test_superuser_sempre_tem_acesso(self):
        user = User.objects.create_superuser(username='super', password='123456', email='a@a.com')
        self.assertTrue(has_module_action(user, 'financeiro', 'excluir'))

    def test_admin_sempre_tem_acesso(self):
        user = User.objects.create_user(username='admin_teste', password='123456')
        user.profile.nivel_acesso = 'ADMIN'
        user.profile.save()
        self.assertTrue(has_module_action(user, 'financeiro', 'excluir'))

    def test_sem_permissao_cadastrada_nega(self):
        user = User.objects.create_user(username='vendedor', password='123456')
        self.assertFalse(has_module_action(user, 'financeiro', 'visualizar'))

    def test_cada_acao_e_independente(self):
        user = User.objects.create_user(username='vendedor2', password='123456')
        PermissaoModulo.objects.create(
            user=user, modulo=self.modulo, pode_visualizar=True, pode_criar=True,
            pode_editar=False, pode_excluir=False,
        )
        self.assertTrue(has_module_action(user, 'financeiro', 'visualizar'))
        self.assertTrue(has_module_action(user, 'financeiro', 'criar'))
        self.assertFalse(has_module_action(user, 'financeiro', 'editar'))
        self.assertFalse(has_module_action(user, 'financeiro', 'excluir'))
