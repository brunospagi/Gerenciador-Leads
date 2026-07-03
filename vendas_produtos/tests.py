from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

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
