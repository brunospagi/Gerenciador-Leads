from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from configuracoes.models import ModuloSistema, PermissaoModulo

from .forms import ClienteForm
from .models import Cliente
from .views import _mapear_status_negociacao_por_andamento


def _liberar_modulo(user, slug, **acoes):
    modulo = ModuloSistema.objects.get(slug=slug)
    valores = {'pode_visualizar': True, 'pode_criar': True, 'pode_editar': True, 'pode_excluir': True}
    valores.update(acoes)
    PermissaoModulo.objects.update_or_create(user=user, modulo=modulo, defaults=valores)


def _criar_cliente(vendedor, **kwargs):
    dados = {
        'vendedor': vendedor,
        'nome_cliente': 'Cliente Teste',
        'whatsapp': '41999990000',
        'tipo_contato': Cliente.TipoContato.MENSAGEM,
        'proximo_passo': Cliente.ProximoPasso.MENSAGEM,
    }
    dados.update(kwargs)
    return Cliente.objects.create(**dados)


class MapearStatusNegociacaoTests(TestCase):
    def test_fechado_com_sucesso_vira_vendido(self):
        resultado = _mapear_status_negociacao_por_andamento(
            Cliente.StatusContato.FECHADO_SUCESSO, Cliente.EtapaFunil.NEGOCIACAO
        )
        self.assertEqual(resultado, Cliente.StatusNegociacao.VENDIDO)

    def test_fechado_com_sucesso_tem_prioridade_sobre_etapa_fechamento(self):
        # Mesmo com etapa_funil=FECHAMENTO, um fechamento com sucesso deve virar VENDIDO, nao FECHAMENTO.
        resultado = _mapear_status_negociacao_por_andamento(
            Cliente.StatusContato.FECHADO_SUCESSO, Cliente.EtapaFunil.FECHAMENTO
        )
        self.assertEqual(resultado, Cliente.StatusNegociacao.VENDIDO)

    def test_sem_interesse_ou_perdido_vira_finalizado(self):
        for status in (Cliente.StatusContato.SEM_INTERESSE, Cliente.StatusContato.PERDIDO):
            with self.subTest(status=status):
                resultado = _mapear_status_negociacao_por_andamento(status, Cliente.EtapaFunil.PROPOSTA)
                self.assertEqual(resultado, Cliente.StatusNegociacao.FINALIZADO)

    def test_etapa_fechamento_sem_status_terminal_vira_fechamento(self):
        resultado = _mapear_status_negociacao_por_andamento(
            Cliente.StatusContato.CONTATO_REALIZADO, Cliente.EtapaFunil.FECHAMENTO
        )
        self.assertEqual(resultado, Cliente.StatusNegociacao.FECHAMENTO)

    def test_aguardando_retorno_vira_pendente(self):
        resultado = _mapear_status_negociacao_por_andamento(
            Cliente.StatusContato.AGUARDANDO_RETORNO, Cliente.EtapaFunil.PROPOSTA
        )
        self.assertEqual(resultado, Cliente.StatusNegociacao.PENDENTE)

    def test_tentativa_ou_nao_contatado_vira_sem_resposta(self):
        for status in (Cliente.StatusContato.TENTATIVA, Cliente.StatusContato.NAO_CONTATADO):
            with self.subTest(status=status):
                resultado = _mapear_status_negociacao_por_andamento(status, Cliente.EtapaFunil.RECEPCAO)
                self.assertEqual(resultado, Cliente.StatusNegociacao.SEM_RESPOSTA)

    def test_contato_realizado_sem_etapa_especial_vira_em_atendimento(self):
        resultado = _mapear_status_negociacao_por_andamento(
            Cliente.StatusContato.CONTATO_REALIZADO, Cliente.EtapaFunil.QUALIFICACAO
        )
        self.assertEqual(resultado, Cliente.StatusNegociacao.EM_ATENDIMENTO)


class EvoCrmIdUnicidadeTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user(username='vendedor_evo_unico', password='123456')

    def test_evo_crm_lead_id_duplicado_gera_erro(self):
        _criar_cliente(self.vendedor, whatsapp='41999990001', evo_crm_lead_id='lead-repetido')

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                _criar_cliente(self.vendedor, whatsapp='41999990002', evo_crm_lead_id='lead-repetido')

    def test_multiplos_clientes_sem_evo_crm_lead_id_nao_conflitam(self):
        # NULL nao deve contar como duplicata (permite varios leads ainda nao sincronizados).
        _criar_cliente(self.vendedor, whatsapp='41999990003')
        _criar_cliente(self.vendedor, whatsapp='41999990004')


class VendedorProtectDeleteTests(TestCase):
    def test_excluir_vendedor_com_leads_e_bloqueado(self):
        vendedor = User.objects.create_user(username='vendedor_com_leads', password='123456')
        _criar_cliente(vendedor, whatsapp='41999990005')

        with self.assertRaises(ProtectedError):
            vendedor.delete()

        # O lead deve continuar existindo normalmente apos a tentativa bloqueada.
        self.assertTrue(Cliente.objects.filter(vendedor=vendedor).exists())


class ClienteFormValorEstimadoTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user(username='vendedor_form_valor', password='123456')

    def _dados_base(self, valor_estimado):
        return {
            'whatsapp': '41999990006',
            'nome_cliente': 'Cliente Form',
            'tipo_veiculo': 'carros',
            'valor_estimado_veiculo': valor_estimado,
            'quantidade_ligacoes': 0,
            'tipo_negociacao': Cliente.TipoNegociacao.VENDA,
            'tipo_contato': Cliente.TipoContato.MENSAGEM,
            'status_negociacao': Cliente.StatusNegociacao.NOVO,
            'status_contato': Cliente.StatusContato.NAO_CONTATADO,
            'etapa_funil': Cliente.EtapaFunil.RECEPCAO,
            'proximo_passo': Cliente.ProximoPasso.MENSAGEM,
            'prioridade': Cliente.Prioridade.MORNO,
            'vendedor': self.vendedor.pk,
        }

    def test_converte_valor_formatado_em_reais_para_decimal(self):
        form = ClienteForm(data=self._dados_base('R$ 45.000,00'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['valor_estimado_veiculo'], Decimal('45000.00'))

    def test_valor_vazio_vira_none(self):
        form = ClienteForm(data=self._dados_base(''))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['valor_estimado_veiculo'])

    def test_valor_nao_numerico_gera_erro(self):
        form = ClienteForm(data=self._dados_base('nao e um numero'))
        self.assertFalse(form.is_valid())
        self.assertIn('valor_estimado_veiculo', form.errors)


class RegistrarAndamentoLeadTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user(username='vendedor_andamento', password='123456')
        _liberar_modulo(self.vendedor, 'clientes')
        self.client.force_login(self.vendedor)
        self.cliente = _criar_cliente(self.vendedor)

    def test_erro_de_validacao_preserva_selecao_e_mostra_mensagem(self):
        # comentario e obrigatorio no model LeadAndamento; omitir de proposito.
        resposta = self.client.post(
            reverse('registrar_andamento_lead', args=[self.cliente.pk]),
            {
                'status_contato': Cliente.StatusContato.CONTATO_REALIZADO,
                'etapa_funil': Cliente.EtapaFunil.QUALIFICACAO,
                'proximo_passo': Cliente.ProximoPasso.MENSAGEM,
            },
        )

        self.assertEqual(resposta.status_code, 200)
        form = resposta.context['lead_andamento_form']
        self.assertIn('comentario', form.errors)
        # A selecao feita pelo usuario deve ser preservada (nao volta para os defaults antigos).
        self.assertEqual(form.data['status_contato'], Cliente.StatusContato.CONTATO_REALIZADO)
        self.assertEqual(form.data['etapa_funil'], Cliente.EtapaFunil.QUALIFICACAO)
        self.cliente.refresh_from_db()
        # Nada deve ter sido salvo no cliente quando a validacao falha.
        self.assertNotEqual(self.cliente.status_contato, Cliente.StatusContato.CONTATO_REALIZADO)

    def test_andamento_valido_atualiza_cliente(self):
        resposta = self.client.post(
            reverse('registrar_andamento_lead', args=[self.cliente.pk]),
            {
                'status_contato': Cliente.StatusContato.CONTATO_REALIZADO,
                'etapa_funil': Cliente.EtapaFunil.QUALIFICACAO,
                'proximo_passo': Cliente.ProximoPasso.MENSAGEM,
                'comentario': 'Cliente respondeu no WhatsApp.',
            },
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.status_contato, Cliente.StatusContato.CONTATO_REALIZADO)
        self.assertEqual(self.cliente.etapa_funil, Cliente.EtapaFunil.QUALIFICACAO)


class MigrationValorEstimadoParseTests(TestCase):
    """
    Regressao: em producao, um valor legado de 'valor_estimado_veiculo' (texto livre)
    estourou a precisao do DecimalField(max_digits=12, decimal_places=2) e derrubou a
    migration inteira com 'numeric field overflow'. A funcao de parse precisa tratar
    esse caso como nao conversivel (None) em vez de deixar o Decimal estourado ir para o save().
    """

    @staticmethod
    def _carregar_parse_valor_estimado():
        import importlib

        modulo = importlib.import_module(
            'clientes.migrations.0012_valor_estimado_veiculo_para_decimal'
        )
        return modulo._parse_valor_estimado

    def test_valor_dentro_da_faixa_e_convertido(self):
        parse = self._carregar_parse_valor_estimado()
        self.assertEqual(parse('R$ 45.000,00'), Decimal('45000.00'))

    def test_valor_que_estoura_precisao_vira_none(self):
        parse = self._carregar_parse_valor_estimado()
        # Lixo/numero de telefone digitado por engano no campo: mais de 10 digitos inteiros.
        self.assertIsNone(parse('11987654321099'))
        self.assertIsNone(parse('999999999999999,00'))

    def test_valor_no_limite_exato_e_aceito(self):
        parse = self._carregar_parse_valor_estimado()
        self.assertEqual(parse('9999999999,99'), Decimal('9999999999.99'))


class ClienteCreateViewWebhookTests(TestCase):
    """Regressao: criar um lead pelo formulario 'Novo Cliente' (ClienteCreateView)
    nunca chamava enviar_webhook_n8n — só o painel de distribuição (PainelDistribuicaoView)
    disparava o webhook. Um lead cadastrado direto por este formulário nunca gerava
    nenhuma notificação pro n8n."""

    def setUp(self):
        self.vendedor = User.objects.create_user('vendedor_webhook', password='senha12345')
        _liberar_modulo(self.vendedor, 'clientes')
        self.client.login(username='vendedor_webhook', password='senha12345')

    @patch('clientes.views.enviar_webhook_n8n')
    def test_criar_cliente_dispara_webhook(self, mock_enviar):
        resp = self.client.post(reverse('cliente_create'), {
            'whatsapp': '41988887777',
            'nome_cliente': 'Lead Novo',
            'tipo_veiculo': 'carros',
            'tipo_contato': Cliente.TipoContato.MENSAGEM,
            'proximo_passo': Cliente.ProximoPasso.MENSAGEM,
            'status_negociacao': Cliente.StatusNegociacao.NOVO,
            'status_contato': Cliente.StatusContato.NAO_CONTATADO,
            'etapa_funil': Cliente.EtapaFunil.RECEPCAO,
            'tipo_negociacao': Cliente.TipoNegociacao.VENDA,
            'prioridade': Cliente.Prioridade.MORNO,
            'quantidade_ligacoes': 0,
        })
        self.assertEqual(resp.status_code, 302)
        cliente = Cliente.objects.get(whatsapp='41988887777')
        mock_enviar.assert_called_once_with(cliente)

    @patch('clientes.views.enviar_webhook_n8n', side_effect=Exception('falha simulada'))
    def test_falha_no_webhook_nao_impede_criacao_do_cliente(self, mock_enviar):
        resp = self.client.post(reverse('cliente_create'), {
            'whatsapp': '41988887778',
            'nome_cliente': 'Lead Novo 2',
            'tipo_veiculo': 'carros',
            'tipo_contato': Cliente.TipoContato.MENSAGEM,
            'proximo_passo': Cliente.ProximoPasso.MENSAGEM,
            'status_negociacao': Cliente.StatusNegociacao.NOVO,
            'status_contato': Cliente.StatusContato.NAO_CONTATADO,
            'etapa_funil': Cliente.EtapaFunil.RECEPCAO,
            'tipo_negociacao': Cliente.TipoNegociacao.VENDA,
            'prioridade': Cliente.Prioridade.MORNO,
            'quantidade_ligacoes': 0,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Cliente.objects.filter(whatsapp='41988887778').exists())


class N8nWebhookUrlSettingTests(TestCase):
    """Regressao: settings.py nunca lia N8N_WEBHOOK_URL do .env (só os outros dois
    webhooks - WEBHOOK_PONTO_URL e N8N_WHATSAPP_WEBHOOK_URL - eram lidos), então o
    fallback de configuracoes.resolver.obter_webhook_url pra DISTRIBUICAO_LEADS nunca
    encontrava uma URL quando o painel não tinha uma cadastrada manualmente."""

    def test_settings_expõe_n8n_webhook_url(self):
        from django.conf import settings
        self.assertTrue(hasattr(settings, 'N8N_WEBHOOK_URL'))
