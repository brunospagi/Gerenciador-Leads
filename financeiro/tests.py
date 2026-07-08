from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from vendas_produtos.models import VendaProduto

from .forms import TransacaoFinanceiraForm
from .models import FechamentoMensalFinanceiro, TransacaoFinanceira, gerar_relatorio_DRE_mensal


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


class TransacaoFinanceiraFormTests(TestCase):
    def test_efetivado_sem_data_pagamento_preenche_automaticamente(self):
        form = TransacaoFinanceiraForm(data={
            'tipo': 'DESPESA', 'categoria': 'OUTROS', 'descricao': 'Teste',
            'valor': '150,00', 'data_vencimento': '2026-03-10',
            'efetivado': 'on', 'recorrente': '',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['data_pagamento'], timezone.localdate())

    def test_nao_efetivado_limpa_data_pagamento(self):
        form = TransacaoFinanceiraForm(data={
            'tipo': 'DESPESA', 'categoria': 'OUTROS', 'descricao': 'Teste',
            'valor': '150,00', 'data_vencimento': '2026-03-10',
            'data_pagamento': '2026-03-10', 'efetivado': '', 'recorrente': '',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['data_pagamento'])


class RecorrenteDuplicacaoTests(TestCase):
    def test_alternar_efetivado_duas_vezes_nao_duplica_mes_seguinte(self):
        transacao = TransacaoFinanceira.objects.create(
            tipo='DESPESA', categoria='FIXA', descricao='Aluguel',
            valor=Decimal('800.00'), data_vencimento=timezone.datetime(2026, 3, 10).date(),
            recorrente=True, efetivado=False,
        )
        # Efetiva -> gera a copia de abril.
        transacao.efetivado = True
        transacao.data_pagamento = timezone.datetime(2026, 3, 10).date()
        transacao.save()
        self.assertEqual(
            TransacaoFinanceira.objects.filter(recorrente=True, data_vencimento__month=4, data_vencimento__year=2026).count(),
            1,
        )

        # Desfaz e refaz "efetivado" -> nao deve duplicar a copia de abril.
        transacao.efetivado = False
        transacao.save()
        transacao.efetivado = True
        transacao.save()

        self.assertEqual(
            TransacaoFinanceira.objects.filter(recorrente=True, data_vencimento__month=4, data_vencimento__year=2026).count(),
            1,
        )


class MesFechadoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin_fin', password='123456')
        self.admin.profile.nivel_acesso = 'ADMIN'
        self.admin.profile.save()
        self.transacao = TransacaoFinanceira.objects.create(
            tipo='DESPESA', categoria='OUTROS', descricao='Conta de teste',
            valor=Decimal('100.00'), data_vencimento=timezone.datetime(2026, 3, 10).date(),
            data_pagamento=timezone.datetime(2026, 3, 10).date(), efetivado=True,
        )
        FechamentoMensalFinanceiro.objects.create(mes=3, ano=2026, fechado=True, fechado_por=self.admin)

    def test_bloqueia_edicao_de_transacao_em_mes_fechado(self):
        self.client.force_login(self.admin)
        url = reverse('financeiro:editar_transacao', kwargs={'pk': self.transacao.pk})
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse('financeiro:lista_transacoes'))

    def test_bloqueia_exclusao_de_transacao_em_mes_fechado(self):
        self.client.force_login(self.admin)
        url = reverse('financeiro:apagar_transacao', kwargs={'pk': self.transacao.pk})
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse('financeiro:lista_transacoes'))
        self.assertTrue(TransacaoFinanceira.objects.filter(pk=self.transacao.pk).exists())

    def test_permite_edicao_apos_reabrir_mes(self):
        FechamentoMensalFinanceiro.objects.filter(mes=3, ano=2026).update(fechado=False)
        self.client.force_login(self.admin)
        url = reverse('financeiro:editar_transacao', kwargs={'pk': self.transacao.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class SaldoListaTests(TestCase):
    def test_saldo_separa_receita_de_despesa(self):
        admin = User.objects.create_user(username='admin_saldo', password='123456')
        admin.profile.nivel_acesso = 'ADMIN'
        admin.profile.save()
        data_ref = timezone.datetime(2026, 5, 15).date()
        TransacaoFinanceira.objects.create(
            tipo='RECEITA', categoria='OUTROS', descricao='Receita', valor=Decimal('1000.00'),
            data_vencimento=data_ref, efetivado=True,
        )
        TransacaoFinanceira.objects.create(
            tipo='DESPESA', categoria='OUTROS', descricao='Despesa', valor=Decimal('800.00'),
            data_vencimento=data_ref, efetivado=True,
        )

        self.client.force_login(admin)
        response = self.client.get(reverse('financeiro:lista_transacoes'), {'mes_ref': '2026-05'})

        self.assertEqual(response.context['receitas_efetivadas'], Decimal('1000.00'))
        self.assertEqual(response.context['despesas_efetivadas'], Decimal('800.00'))
        self.assertEqual(response.context['saldo_geral'], Decimal('200.00'))
