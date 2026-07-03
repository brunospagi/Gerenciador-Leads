from datetime import datetime, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from clientes.models import Cliente
from controle_ponto.models import RegistroPonto
from funcionarios.models import Funcionario
from distribuicao.forms import LeadEntradaForm
from distribuicao.logic import criar_lead_evo_crm, definir_proximo_vendedor
from distribuicao.models import VendedorRodizio


class DistribuicaoRegrasPontoTests(TestCase):
    def _criar_vendedor(self, username='vendedor1'):
        user = User(username=username)
        user.set_password('123456')
        # Evita perfil funcional automático do signal; o teste cria o Funcionario explicitamente abaixo.
        user._skip_funcionario_signal = True
        user.save()
        funcionario = Funcionario.objects.create(
            user=user,
            cpf=f"000.000.000-{str(user.id).zfill(2)}",
            telefone='41999999999',
            endereco='Rua Teste, 123',
            cargo='Vendedor',
            data_admissao=timezone.localdate(),
            salario_base=Decimal('2500.00'),
            banco='Banco Teste',
            agencia='0001',
            conta=f'{user.id}2345',
            tipo_conta='CORRENTE',
        )
        VendedorRodizio.objects.create(vendedor=user, ativo=True, ordem=1)
        return user, funcionario

    def _agora(self, hora, minuto=0):
        data = timezone.localdate()
        naive = datetime.combine(data, time(hora, minuto))
        return timezone.make_aware(naive)

    def test_permite_distribuicao_antes_14_sem_saida_almoco(self):
        user, funcionario = self._criar_vendedor('vendedor_antes_14')
        RegistroPonto.objects.create(funcionario=funcionario, entrada=time(8, 0))

        with patch('distribuicao.logic.timezone.localtime', return_value=self._agora(13, 30)):
            proximo = definir_proximo_vendedor()

        self.assertEqual(proximo, user)

    def test_manha_permite_entrada_com_atraso(self):
        user, funcionario = self._criar_vendedor('vendedor_atrasado_manha')
        RegistroPonto.objects.create(
            funcionario=funcionario,
            entrada=time(8, 20),
            atraso_minutos=20,
        )

        with patch('distribuicao.logic.timezone.localtime', return_value=self._agora(10, 0)):
            proximo = definir_proximo_vendedor()

        self.assertEqual(proximo, user)

    def test_tarde_antes_14_nao_exige_saida_almoco(self):
        user, funcionario = self._criar_vendedor('vendedor_livre_ate_14')
        RegistroPonto.objects.create(
            funcionario=funcionario,
            entrada=time(8, 0),
            atraso_minutos=0,
            saida_almoco=None,
            retorno_almoco=None,
        )

        with patch('distribuicao.logic.timezone.localtime', return_value=self._agora(13, 45)):
            proximo = definir_proximo_vendedor()

        self.assertEqual(proximo, user)

    def test_bloqueia_distribuicao_apos_14_sem_saida_almoco(self):
        _, funcionario = self._criar_vendedor('vendedor_sem_saida_14')
        RegistroPonto.objects.create(funcionario=funcionario, entrada=time(8, 0))

        with patch('distribuicao.logic.timezone.localtime', return_value=self._agora(14, 1)):
            proximo = definir_proximo_vendedor()

        self.assertIsNone(proximo)

    def test_bloqueia_entre_saida_e_retorno_almoco(self):
        _, funcionario = self._criar_vendedor('vendedor_no_almoco')
        RegistroPonto.objects.create(
            funcionario=funcionario,
            entrada=time(8, 0),
            saida_almoco=time(12, 0),
            retorno_almoco=None,
        )

        with patch('distribuicao.logic.timezone.localtime', return_value=self._agora(13, 0)):
            proximo = definir_proximo_vendedor()

        self.assertIsNone(proximo)

    def test_permite_quando_ja_retornou_almoco(self):
        user, funcionario = self._criar_vendedor('vendedor_retornou')
        RegistroPonto.objects.create(
            funcionario=funcionario,
            entrada=time(8, 0),
            saida_almoco=time(12, 0),
            retorno_almoco=time(13, 0),
        )

        with patch('distribuicao.logic.timezone.localtime', return_value=self._agora(14, 30)):
            proximo = definir_proximo_vendedor()

        self.assertEqual(proximo, user)

    def test_rodizio_alterna_entre_vendedores_elegiveis(self):
        user_a, funcionario_a = self._criar_vendedor('vendedor_rodizio_a')
        user_b, funcionario_b = self._criar_vendedor('vendedor_rodizio_b')
        for funcionario in (funcionario_a, funcionario_b):
            RegistroPonto.objects.create(funcionario=funcionario, entrada=time(8, 0))

        VendedorRodizio.objects.filter(vendedor=user_a).update(ordem=1)
        VendedorRodizio.objects.filter(vendedor=user_b).update(ordem=2)

        with patch('distribuicao.logic.timezone.localtime', return_value=self._agora(10, 0)):
            primeiro = definir_proximo_vendedor()
            segundo = definir_proximo_vendedor()
            terceiro = definir_proximo_vendedor()

        # Primeira rodada respeita a ordem cadastrada; depois alterna por quem foi atribuido ha mais tempo.
        self.assertEqual(primeiro, user_a)
        self.assertEqual(segundo, user_b)
        self.assertEqual(terceiro, user_a)


class LeadEntradaFormDedupTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user(username='vendedor_dedup', password='123456')

    def _dados_base(self, whatsapp):
        return {
            'nome_cliente': 'Cliente Teste',
            'email': 'cliente@teste.com',
            'whatsapp': whatsapp,
            'tipo_veiculo': 'carros',
            'marca_veiculo': 'Honda',
            'modelo_veiculo': 'Civic',
            'fonte_cliente': 'Instagram',
            'observacao': '',
        }

    def test_detecta_duplicata_com_formatacao_diferente(self):
        Cliente.objects.create(
            vendedor=self.vendedor,
            nome_cliente='Cliente Existente',
            whatsapp='(41) 99999-1111',
            tipo_contato=Cliente.TipoContato.MENSAGEM,
            proximo_passo=Cliente.ProximoPasso.MENSAGEM,
        )

        # Mesmo numero, digitado sem formatacao: precisa ser detectado como duplicata.
        form = LeadEntradaForm(data=self._dados_base('41999991111'))

        self.assertFalse(form.is_valid())
        self.assertIn('whatsapp', form.errors)

    def test_nao_marca_falso_positivo_por_substring(self):
        Cliente.objects.create(
            vendedor=self.vendedor,
            nome_cliente='Cliente Existente',
            whatsapp='(41) 41987-6543',
            tipo_contato=Cliente.TipoContato.MENSAGEM,
            proximo_passo=Cliente.ProximoPasso.MENSAGEM,
        )

        # "9876543" e substring dos digitos acima, mas e um numero diferente de verdade.
        form = LeadEntradaForm(data=self._dados_base('9876543'))

        self.assertTrue(form.is_valid())


class VerificarDuplicidadeWhatsappViewTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user(username='vendedor_ajax', password='123456')
        self.vendedor.module_permissions.modulo_distribuicao = True
        self.vendedor.module_permissions.save()
        self.client.force_login(self.vendedor)

    def test_retorna_duplicado_true_quando_ja_existe(self):
        Cliente.objects.create(
            vendedor=self.vendedor,
            nome_cliente='Cliente Existente',
            whatsapp='(41) 99999-1111',
            tipo_contato=Cliente.TipoContato.MENSAGEM,
            proximo_passo=Cliente.ProximoPasso.MENSAGEM,
        )

        resposta = self.client.get('/distribuicao/verificar-duplicidade/', {'whatsapp': '41999991111'})

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados['duplicado'])
        self.assertIn('vendedor_nome', dados)
        self.assertIn('data_entrada', dados)

    def test_retorna_duplicado_false_quando_nao_existe(self):
        resposta = self.client.get('/distribuicao/verificar-duplicidade/', {'whatsapp': '41988887777'})

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.json()['duplicado'])

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get('/distribuicao/verificar-duplicidade/', {'whatsapp': '41988887777'})
        self.assertNotEqual(resposta.status_code, 200)


@override_settings(
    EVO_CRM_API_URL='https://api.evoai.app',
    EVO_CRM_API_TOKEN='token-teste',
    EVO_CRM_PIPELINE_ID='ec29bfe0-4104-4a3c-a85a-d9868fdc773d',
    EVO_CRM_PIPELINE_STAGE_ID='7e472e0c-6a1b-4853-9708-3cec505be167',
    EVO_CRM_TIMEOUT_SECONDS=4,
)
class DistribuicaoEvoCrmTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='vendedor_evo', password='123456')
        self.cliente = Cliente.objects.create(
            vendedor=self.user,
            nome_cliente='Maria da Silva',
            email='maria@teste.com',
            whatsapp='(41) 99999-1111',
            tipo_veiculo='carros',
            marca_veiculo='Honda',
            modelo_veiculo='Civic',
            fonte_cliente='Instagram',
            data_proximo_contato=timezone.now(),
            tipo_contato=Cliente.TipoContato.MENSAGEM,
            proximo_passo=Cliente.ProximoPasso.MENSAGEM,
        )

    @patch('distribuicao.logic.requests.post')
    def test_cria_lead_no_evo_crm_e_salva_ids(self, mock_post):
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {
                'lead_id': 'lead-uuid-1',
                'deal_id': 'deal-uuid-1',
            },
        }
        mock_post.return_value.raise_for_status.return_value = None

        resultado = criar_lead_evo_crm(self.cliente)

        self.assertTrue(resultado['success'])
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.evo_crm_lead_id, 'lead-uuid-1')
        self.assertEqual(self.cliente.evo_crm_deal_id, 'deal-uuid-1')
        self.assertEqual(self.cliente.evo_crm_pipeline_id, 'ec29bfe0-4104-4a3c-a85a-d9868fdc773d')

        chamada = mock_post.call_args.kwargs
        self.assertEqual(chamada['headers']['api_access_token'], 'token-teste')
        self.assertEqual(chamada['json']['deal']['pipeline_id'], 'ec29bfe0-4104-4a3c-a85a-d9868fdc773d')
        self.assertEqual(chamada['json']['deal']['stage_id'], '7e472e0c-6a1b-4853-9708-3cec505be167')
        self.assertEqual(chamada['json']['contact']['email'], 'maria@teste.com')
        self.assertEqual(chamada['json']['contact']['phone_number'], '+5541999991111')
        self.assertEqual(chamada['json']['contact']['name'], 'Maria da Silva')
        self.assertNotIn('source_id', chamada['json']['contact'])

    @patch('distribuicao.logic.requests.post')
    def test_trata_como_sucesso_quando_api_nao_retorna_ids(self, mock_post):
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {},
        }
        mock_post.return_value.raise_for_status.return_value = None

        resultado = criar_lead_evo_crm(self.cliente)

        self.assertTrue(resultado['success'])
        self.assertTrue(resultado['skipped'])
        self.assertEqual(resultado['reason'], 'created_without_ids')
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.evo_crm_pipeline_id, 'ec29bfe0-4104-4a3c-a85a-d9868fdc773d')
        self.assertIsNone(self.cliente.evo_crm_lead_id)
        self.assertIsNone(self.cliente.evo_crm_deal_id)

    @override_settings(EVO_CRM_API_TOKEN='', EVO_CRM_PIPELINE_ID='')
    @patch('distribuicao.logic.requests.post')
    def test_nao_chama_api_sem_configuracao(self, mock_post):
        resultado = criar_lead_evo_crm(self.cliente)

        self.assertFalse(resultado['success'])
        self.assertTrue(resultado['skipped'])
        self.assertEqual(resultado['reason'], 'not_configured')
        mock_post.assert_not_called()

    @patch('distribuicao.logic.requests.post')
    def test_comando_sincronizar_evo_crm_reprocessa_pendentes(self, mock_post):
        from io import StringIO
        from django.core.management import call_command

        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {'lead_id': 'lead-retry-1', 'deal_id': 'deal-retry-1'},
        }
        mock_post.return_value.raise_for_status.return_value = None

        self.assertIsNone(self.cliente.evo_crm_lead_id)

        saida = StringIO()
        call_command('sincronizar_evo_crm', stdout=saida)

        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.evo_crm_lead_id, 'lead-retry-1')
        self.assertEqual(self.cliente.evo_crm_deal_id, 'deal-retry-1')
        self.assertIn('1 sincronizado(s)', saida.getvalue())

    @patch('distribuicao.logic.requests.post')
    def test_comando_sincronizar_evo_crm_ignora_ja_sincronizados(self, mock_post):
        from io import StringIO
        from django.core.management import call_command

        self.cliente.evo_crm_lead_id = 'lead-ja-sincronizado'
        self.cliente.evo_crm_deal_id = 'deal-ja-sincronizado'
        self.cliente.save(update_fields=['evo_crm_lead_id', 'evo_crm_deal_id'])

        saida = StringIO()
        call_command('sincronizar_evo_crm', stdout=saida)

        mock_post.assert_not_called()
        self.assertIn('Nenhum lead pendente', saida.getvalue())
