import io

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import FOTO_BIOMETRIA_MAX_SIZE_MB, Funcionario, cpf_temporario_por_user_id


def _gerar_imagem_png(largura=10, altura=10):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new('RGB', (largura, altura), color='red').save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.read()


def _gerar_imagem_png_sem_compressao(largura, altura):
    # Ruido aleatorio + compress_level=0 gera um PNG proximo do tamanho bruto (largura*altura*3),
    # permitindo testar o limite de tamanho de forma previsivel.
    import os

    from PIL import Image

    raw = os.urandom(largura * altura * 3)
    imagem = Image.frombytes('RGB', (largura, altura), raw)
    buffer = io.BytesIO()
    imagem.save(buffer, format='PNG', compress_level=0)
    buffer.seek(0)
    return buffer.read()


class FuncionarioFotoBiometriaTests(TestCase):
    def setUp(self):
        user = User(username='colaborador_teste')
        user.set_password('123456')
        # Evita o Funcionario automatico do signal; este teste monta o proprio objeto (nao salvo).
        user._skip_funcionario_signal = True
        user.save()
        self.funcionario = Funcionario(
            user=user,
            cpf='000.000.000-01',
            telefone='41999999999',
            endereco='Rua Teste, 123',
            cargo='Vendedor',
            salario_base=2500,
            banco='Banco Teste',
            agencia='0001',
            conta='12345',
        )

    def test_aceita_imagem_png_valida(self):
        self.funcionario.foto_biometria = SimpleUploadedFile(
            'foto.png', _gerar_imagem_png(), content_type='image/png'
        )
        self.funcionario.full_clean(exclude=['data_admissao'])

    def test_rejeita_extensao_nao_permitida(self):
        self.funcionario.foto_biometria = SimpleUploadedFile(
            'foto.gif', _gerar_imagem_png(), content_type='image/gif'
        )
        with self.assertRaises(ValidationError):
            self.funcionario.full_clean(exclude=['data_admissao'])

    def test_rejeita_arquivo_maior_que_limite(self):
        # 1600x1300x3 bytes sem compressao (~6.2MB) excede o limite configurado (5MB).
        conteudo = _gerar_imagem_png_sem_compressao(1600, 1300)
        self.assertGreater(len(conteudo), FOTO_BIOMETRIA_MAX_SIZE_MB * 1024 * 1024)
        self.funcionario.foto_biometria = SimpleUploadedFile(
            'foto.png', conteudo, content_type='image/png'
        )
        with self.assertRaises(ValidationError):
            self.funcionario.full_clean(exclude=['data_admissao'])


class FuncionarioCpfPendenteTests(TestCase):
    def test_signal_cria_cpf_placeholder_marcado_como_pendente(self):
        user = User.objects.create_user(username='colaborador_signal', password='123456')

        funcionario = user.dados_funcionais
        self.assertEqual(funcionario.cpf, cpf_temporario_por_user_id(user.id))
        self.assertTrue(funcionario.cpf_pendente)

    def test_cpf_real_nao_e_marcado_como_pendente(self):
        user = User(username='colaborador_com_cpf_real')
        user._skip_funcionario_signal = True
        user.save()
        funcionario = Funcionario.objects.create(
            user=user,
            cpf='123.456.789-00',
            telefone='41999999999',
            endereco='Rua Teste, 123',
            cargo='Vendedor',
            data_admissao='2026-01-01',
            salario_base=2500,
            banco='Banco Teste',
            agencia='0001',
            conta='12345',
        )

        self.assertFalse(funcionario.cpf_pendente)
