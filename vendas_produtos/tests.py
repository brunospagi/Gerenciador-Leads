from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import ParametrosComissao, VendaProduto


class ComissaoVendaProdutoTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user(username='vendedor_comissao', password='123456')
        self.ajudante = User.objects.create_user(username='ajudante_comissao', password='123456')
        # Garante os defaults conhecidos do painel de comissoes (independente de outros testes).
        self.config = ParametrosComissao.get_solo()

    def _criar_venda(self, **kwargs):
        dados = {
            'vendedor': self.vendedor,
            'cliente_nome': 'Cliente Teste',
            'placa': 'ABC1D23',
            'modelo_veiculo': 'Civic',
            'valor_venda': Decimal('0'),
            'custo_base': Decimal('0'),
        }
        dados.update(kwargs)
        return VendaProduto.objects.create(**dados)

    def test_venda_veiculo_sem_desconto_usa_comissao_padrao(self):
        venda = self._criar_venda(
            tipo_produto='VENDA_VEICULO',
            valor_venda=Decimal('50000.00'),
            custo_base=Decimal('40000.00'),
            com_desconto=False,
        )

        self.assertEqual(venda.comissao_vendedor, self.config.comissao_carro_padrao)
        self.assertEqual(venda.comissao_ajudante, Decimal('0.00'))
        self.assertEqual(venda.lucro_loja, Decimal('50000.00') - Decimal('40000.00') - self.config.comissao_carro_padrao)

    def test_venda_veiculo_com_desconto_usa_comissao_reduzida(self):
        venda = self._criar_venda(
            tipo_produto='VENDA_VEICULO',
            valor_venda=Decimal('48000.00'),
            custo_base=Decimal('40000.00'),
            com_desconto=True,
        )

        self.assertEqual(venda.comissao_vendedor, self.config.comissao_carro_desconto)

    def test_venda_veiculo_com_ajudante_faz_split(self):
        venda = self._criar_venda(
            tipo_produto='VENDA_VEICULO',
            valor_venda=Decimal('50000.00'),
            custo_base=Decimal('40000.00'),
            vendedor_ajudante=self.ajudante,
        )

        comissao_total = self.config.comissao_carro_padrao
        pct_ajudante = self.config.split_ajudante
        self.assertEqual(venda.comissao_ajudante, comissao_total * pct_ajudante)
        self.assertEqual(venda.comissao_vendedor, comissao_total * (Decimal('1.00') - pct_ajudante))
        # A soma dos splits deve bater com a comissao total (sem perda por arredondamento neste cenario).
        self.assertEqual(venda.comissao_vendedor + venda.comissao_ajudante, comissao_total)

    def test_garantia_abaixo_do_preco_base_zera_comissao_vendedor(self):
        venda = self._criar_venda(
            tipo_produto='GARANTIA',
            valor_venda=self.config.garantia_base - Decimal('1.00'),
        )

        self.assertEqual(venda.comissao_vendedor, Decimal('0.00'))
        self.assertEqual(venda.lucro_loja, self.config.garantia_base - self.config.garantia_custo)

    def test_garantia_acima_do_preco_base_repassa_diferenca_ao_vendedor(self):
        venda = self._criar_venda(
            tipo_produto='GARANTIA',
            valor_venda=self.config.garantia_base + Decimal('200.00'),
        )

        self.assertEqual(venda.comissao_vendedor, Decimal('200.00'))

    def test_refinanciamento_usa_split_configurado(self):
        venda = self._criar_venda(
            tipo_produto='REFINANCIAMENTO',
            valor_venda=Decimal('10000.00'),
        )

        split_vendedor = self.config.split_refin
        self.assertEqual(venda.comissao_vendedor, Decimal('10000.00') * split_vendedor)
        self.assertEqual(venda.lucro_loja, Decimal('10000.00') * (Decimal('1.00') - split_vendedor))

    def test_refinanciamento_sem_valor_nao_gera_comissao(self):
        venda = self._criar_venda(
            tipo_produto='REFINANCIAMENTO',
            valor_venda=Decimal('0.00'),
        )

        self.assertEqual(venda.comissao_vendedor, Decimal('0.00'))
        self.assertEqual(venda.lucro_loja, Decimal('0.00'))

    def test_transferencia_com_prejuizo_nao_gera_comissao_negativa(self):
        venda = self._criar_venda(
            tipo_produto='TRANSFERENCIA',
            valor_venda=Decimal('100.00'),
            custo_base=Decimal('300.00'),
        )

        self.assertEqual(venda.comissao_vendedor, Decimal('0.00'))
        self.assertEqual(venda.lucro_loja, Decimal('0.00'))


class RejeitarVendaWhatsappTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user(username='vendedor_rejeicao', password='123456')
        self.vendedor.dados_funcionais.telefone = '41988887777'
        self.vendedor.dados_funcionais.save()

        # Admin que RECEBE a notificacao (distinto de quem rejeita, pra nao se autonotificar).
        self.admin = User.objects.create_user(username='admin_rejeicao', password='123456')
        self.admin.profile.nivel_acesso = 'ADMIN'
        self.admin.profile.save()
        self.admin.dados_funcionais.telefone = '41977776666'
        self.admin.dados_funcionais.save()

        # Quem executa a rejeicao (superuser: bypassa o middleware de modulo sem precisar
        # de PermissaoModulo extra, e _is_gestor_financeiro aceita superuser).
        self.gerente = User.objects.create_superuser(
            username='gerente_rejeicao', password='123456', email='gerente@teste.com',
        )

        self.venda = VendaProduto.objects.create(
            vendedor=self.vendedor,
            cliente_nome='Cliente Rejeitado',
            placa='REJ0001',
            modelo_veiculo='Onix',
            tipo_produto='VENDA_VEICULO',
            valor_venda=Decimal('50000.00'),
            custo_base=Decimal('40000.00'),
        )

    @patch('notificacoes.whatsapp.enviar_webhook')
    def test_rejeitar_venda_dispara_whatsapp_pro_vendedor_e_admins(self, mock_enviar):
        self.client.force_login(self.gerente)
        self.client.post(
            reverse('venda_produto_reject', kwargs={'pk': self.venda.pk}),
            {'motivo_recusa': 'Comprovante inválido'},
        )

        self.venda.refresh_from_db()
        self.assertEqual(self.venda.status, 'REJEITADO')
        self.assertEqual(mock_enviar.call_count, 2)
        telefones_notificados = {call.args[1]['telefone'] for call in mock_enviar.call_args_list}
        self.assertEqual(telefones_notificados, {'41988887777', '41977776666'})

    @patch('notificacoes.whatsapp.enviar_webhook')
    def test_nao_dispara_whatsapp_se_vendedor_desativou_notificacao(self, mock_enviar):
        self.vendedor.profile.notificacao_whatsapp = False
        self.vendedor.profile.save()

        self.client.force_login(self.gerente)
        self.client.post(
            reverse('venda_produto_reject', kwargs={'pk': self.venda.pk}),
            {'motivo_recusa': 'Comprovante inválido'},
        )

        # So o admin recebe; vendedor desativou.
        mock_enviar.assert_called_once()
        args, _ = mock_enviar.call_args
        self.assertEqual(args[1]['telefone'], '41977776666')


class VendaProdutoDuplicidadeTests(TestCase):
    """Regressao: a guarda anti-duplo-envio antiga só olhava se já existia uma
    venda igual criada nos últimos 25s ("olha antes de criar", sem lock nem
    constraint) — duas requisições quase simultâneas (duplo clique rápido,
    reenvio de rede) podiam passar as duas pela checagem antes de qualquer
    uma terminar de gravar, duplicando a venda. Agora o idempotency_key
    (token gerado no navegador, reenviado igual em qualquer reenvio do MESMO
    envio) tem unique constraint no banco, que bloqueia de verdade."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin_dup_venda', password='123456', email='admin_dup@teste.com',
        )

    def _dados_post(self, **overrides):
        # GARANTIA exige valor_venda >= 1300 e a soma dos pagamentos batendo
        # com o valor total (model.clean()) — pgto_pix igual ao valor_venda
        # satisfaz as duas coisas nos testes abaixo.
        valor = overrides.pop('valor_venda', '1500.00')
        dados = {
            'vendedor': self.admin.pk,
            'tipo_produto': 'GARANTIA',
            'com_desconto': 'False',
            'cliente_nome': 'Cliente Duplicidade',
            'origem_cliente': 'OUTRO',
            'modelo_veiculo': 'Onix',
            'placa': 'DUP0001',
            'valor_venda': valor,
            'pgto_debito': valor,
            'data_venda': '2026-01-10',
            'idempotency_key': 'token-teste-abc123',
        }
        dados.update(overrides)
        return dados

    def test_idempotency_key_e_unico_no_banco(self):
        VendaProduto.objects.create(
            vendedor=self.admin, tipo_produto='GARANTIA', cliente_nome='Cliente 1',
            placa='DUP0001', valor_venda=Decimal('1000.00'), idempotency_key='token-repetido',
        )
        with self.assertRaises(Exception):
            VendaProduto.objects.create(
                vendedor=self.admin, tipo_produto='GARANTIA', cliente_nome='Cliente 2',
                placa='DUP0002', valor_venda=Decimal('2000.00'), idempotency_key='token-repetido',
            )

    def test_varias_vendas_sem_token_nao_conflitam(self):
        # idempotency_key nulo (fluxos que nao mandam token) nao deve colidir
        # entre si — NULL != NULL na constraint unica.
        VendaProduto.objects.create(
            vendedor=self.admin, tipo_produto='GARANTIA', cliente_nome='Cliente 1',
            placa='DUP0003', valor_venda=Decimal('1000.00'),
        )
        VendaProduto.objects.create(
            vendedor=self.admin, tipo_produto='GARANTIA', cliente_nome='Cliente 2',
            placa='DUP0004', valor_venda=Decimal('2000.00'),
        )
        self.assertEqual(VendaProduto.objects.count(), 2)

    def test_reenvio_com_mesmo_token_nao_duplica(self):
        self.client.force_login(self.admin)
        dados = self._dados_post()

        resp1 = self.client.post(reverse('venda_produto_create'), dados)
        self.assertEqual(resp1.status_code, 302)
        self.assertEqual(VendaProduto.objects.filter(idempotency_key='token-teste-abc123').count(), 1)

        # Simula o reenvio do MESMO formulário (duplo clique/retry) — mesmo token.
        resp2 = self.client.post(reverse('venda_produto_create'), dados)
        self.assertEqual(resp2.status_code, 302)

        self.assertEqual(VendaProduto.objects.filter(cliente_nome='Cliente Duplicidade').count(), 1)

    def test_tokens_diferentes_permitem_duas_vendas_legitimas(self):
        self.client.force_login(self.admin)

        # Placa/valor diferentes pra não cair na checagem de janela de tempo
        # (essa é intencional: bloqueia vendas com os MESMOS dados em poucos
        # segundos, o que este teste não quer exercitar) — o que se quer
        # confirmar aqui é só que tokens diferentes não geram falso positivo.
        resp1 = self.client.post(
            reverse('venda_produto_create'),
            self._dados_post(idempotency_key='token-1', placa='DUP0005', valor_venda='1500.00'),
        )
        self.assertEqual(resp1.status_code, 302)
        resp2 = self.client.post(
            reverse('venda_produto_create'),
            self._dados_post(idempotency_key='token-2', placa='DUP0006', valor_venda='2500.00'),
        )
        self.assertEqual(resp2.status_code, 302)

        self.assertEqual(VendaProduto.objects.filter(cliente_nome='Cliente Duplicidade').count(), 2)
