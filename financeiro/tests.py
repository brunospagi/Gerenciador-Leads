from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from vendas_produtos.models import VendaProduto

from .models import TransacaoFinanceira, gerar_relatorio_DRE_mensal


class DreMensalTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user(username='vendedor_dre', password='123456')
        self.mes = 3
        self.ano = 2026
        self.data_ref = timezone.datetime(self.ano, self.mes, 15).date()

    def test_venda_nao_aprovada_nao_entra_no_dre(self):
        VendaProduto.objects.create(
            vendedor=self.vendedor,
            cliente_nome='Cliente Pendente',
            placa='PEN0001',
            modelo_veiculo='Onix',
            tipo_produto='VENDA_VEICULO',
            valor_venda=Decimal('50000.00'),
            custo_base=Decimal('40000.00'),
            data_venda=self.data_ref,
            status='PENDENTE',
        )

        relatorio = gerar_relatorio_DRE_mensal(self.mes, self.ano)

        self.assertEqual(relatorio['lucro_vendas'], 0)
        self.assertEqual(relatorio['total_entradas'], 0)

    def test_venda_aprovada_soma_lucro_e_comissao_embutida(self):
        venda = VendaProduto.objects.create(
            vendedor=self.vendedor,
            cliente_nome='Cliente Aprovado',
            placa='APR0001',
            modelo_veiculo='Civic',
            tipo_produto='VENDA_VEICULO',
            valor_venda=Decimal('50000.00'),
            custo_base=Decimal('40000.00'),
            data_venda=self.data_ref,
            status='APROVADO',
        )

        relatorio = gerar_relatorio_DRE_mensal(self.mes, self.ano)

        self.assertEqual(relatorio['lucro_vendas'], venda.lucro_loja)
        self.assertEqual(relatorio['comissao_total_vendas'], venda.comissao_vendedor + venda.comissao_ajudante)
        # O lucro "antes da comissao" deve somar de volta a comissao ja embutida no lucro_loja.
        self.assertEqual(
            relatorio['lucro_vendas_antes_comissao'],
            venda.lucro_loja + venda.comissao_vendedor + venda.comissao_ajudante,
        )
        self.assertEqual(relatorio['total_entradas'], relatorio['lucro_vendas_antes_comissao'])

    def test_receitas_e_despesas_efetivadas_entram_no_saldo(self):
        TransacaoFinanceira.objects.create(
            tipo='RECEITA', categoria='OUTROS', descricao='Receita extra',
            valor=Decimal('1000.00'), data_vencimento=self.data_ref,
            data_pagamento=self.data_ref, efetivado=True,
        )
        TransacaoFinanceira.objects.create(
            tipo='DESPESA', categoria='FIXA', descricao='Aluguel',
            valor=Decimal('800.00'), data_vencimento=self.data_ref,
            data_pagamento=self.data_ref, efetivado=True,
        )
        # Nao efetivada: nao deve entrar no calculo.
        TransacaoFinanceira.objects.create(
            tipo='DESPESA', categoria='FIXA', descricao='Conta em aberto',
            valor=Decimal('500.00'), data_vencimento=self.data_ref,
            efetivado=False,
        )

        relatorio = gerar_relatorio_DRE_mensal(self.mes, self.ano)

        self.assertEqual(relatorio['receitas_extras'], Decimal('1000.00'))
        self.assertEqual(relatorio['despesas_loja'], Decimal('800.00'))
        self.assertEqual(relatorio['total_entradas'], Decimal('1000.00'))
        self.assertEqual(relatorio['total_saidas'], Decimal('800.00'))
        self.assertEqual(relatorio['saldo_liquido'], Decimal('200.00'))
