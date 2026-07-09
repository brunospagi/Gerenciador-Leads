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
