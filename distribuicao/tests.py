from datetime import datetime, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from controle_ponto.models import RegistroPonto
from funcionarios.models import Funcionario
from distribuicao.logic import definir_proximo_vendedor
from distribuicao.models import VendedorRodizio


class DistribuicaoRegrasPontoTests(TestCase):
    def _criar_vendedor(self, username='vendedor1'):
        user = User.objects.create_user(username=username, password='123456')
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
