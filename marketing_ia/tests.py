import base64
import io
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase
from PIL import Image

from . import ai_promocional
from . import image_overlay
from . import leonardo_client
from . import openai_client


class OpenAIClientTests(TestCase):
    def _mock_response(self, status_code, json_data=None, text=''):
        resp = Mock()
        resp.status_code = status_code
        resp.ok = status_code < 400
        resp.json.return_value = json_data or {}
        resp.text = text
        return resp

    @patch('marketing_ia.openai_client.requests.post')
    def test_gera_imagem_com_sucesso(self, mock_post):
        imagem_falsa = b'conteudo-fake-da-imagem'
        b64 = base64.b64encode(imagem_falsa).decode('utf-8')
        mock_post.return_value = self._mock_response(
            200,
            {'data': [{'b64_json': b64}], 'output_format': 'jpeg'},
        )

        imagem_bytes, mime_type = openai_client.gerar_imagem_openai(
            'prompt de teste', b'foto-original', 'image/jpeg', 'chave-fake',
        )

        self.assertEqual(imagem_bytes, imagem_falsa)
        self.assertEqual(mime_type, 'image/jpeg')

        # Confere que o request foi montado como multipart/form-data com os
        # campos esperados (endpoint, model, prompt, quality padrao, imagem de referência).
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], f'{openai_client.BASE_URL}/images/edits')
        self.assertEqual(kwargs['data']['model'], openai_client.MODEL_ID_PADRAO)
        self.assertEqual(kwargs['data']['prompt'], 'prompt de teste')
        self.assertEqual(kwargs['data']['quality'], 'medium')
        self.assertIn('image', kwargs['files'])
        self.assertEqual(kwargs['headers']['authorization'], 'Bearer chave-fake')

    @patch('marketing_ia.openai_client.requests.post')
    def test_model_id_e_quality_configurados_sao_repassados(self, mock_post):
        imagem_falsa = b'conteudo-fake'
        b64 = base64.b64encode(imagem_falsa).decode('utf-8')
        mock_post.return_value = self._mock_response(
            200, {'data': [{'b64_json': b64}], 'output_format': 'jpeg'},
        )

        openai_client.gerar_imagem_openai(
            'prompt', b'foto', 'image/jpeg', 'chave-fake',
            model_id='gpt-image-2', quality='high',
        )

        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs['data']['model'], 'gpt-image-2')
        self.assertEqual(kwargs['data']['quality'], 'high')

    @patch('marketing_ia.openai_client.requests.post')
    def test_erro_de_creditos_insuficientes_vira_openai_image_error(self, mock_post):
        # Reproduz o erro real reportado em producao (HTTP 400, sem creditos na conta).
        mock_post.return_value = self._mock_response(
            400,
            {'error': {'message': 'not enough api tokens userId: fb4879e6-...'}},
            text='{"error":{"message":"not enough api tokens userId: fb4879e6-..."}}',
        )

        with self.assertRaises(openai_client.OpenAIImageError) as ctx:
            openai_client.gerar_imagem_openai('prompt', b'foto', 'image/jpeg', 'chave-fake')

        self.assertIn('not enough api tokens', str(ctx.exception))

    @patch('marketing_ia.openai_client.requests.post')
    def test_resposta_sem_b64_json_vira_erro(self, mock_post):
        mock_post.return_value = self._mock_response(200, {'data': []})

        with self.assertRaises(openai_client.OpenAIImageError):
            openai_client.gerar_imagem_openai('prompt', b'foto', 'image/jpeg', 'chave-fake')


class LeonardoClientTests(TestCase):
    def test_model_id_configurado_e_repassado_na_generation(self):
        # _criar_generation e a funcao que efetivamente monta o payload de /generations
        # com o modelId - testada isolada pra nao precisar mockar o fluxo inteiro
        # (init-image + upload + generations + polling).
        with patch('marketing_ia.leonardo_client.requests.post') as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {'generationId': 'gen-123'},
            )
            mock_post.return_value.raise_for_status = lambda: None

            generation_id = leonardo_client._criar_generation(
                'chave-fake', 'prompt de teste', 'init-image-id', 'modelo-customizado-id',
            )

            self.assertEqual(generation_id, 'gen-123')
            _, kwargs = mock_post.call_args
            self.assertEqual(kwargs['json']['modelId'], 'modelo-customizado-id')

    def test_model_id_padrao_e_usado_quando_nao_informado(self):
        with patch('marketing_ia.leonardo_client.requests.post') as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {'generationId': 'gen-456'},
            )
            mock_post.return_value.raise_for_status = lambda: None

            leonardo_client._criar_generation(
                'chave-fake', 'prompt', 'init-image-id', leonardo_client.MODEL_ID_PADRAO,
            )

            _, kwargs = mock_post.call_args
            self.assertEqual(kwargs['json']['modelId'], leonardo_client.MODEL_ID_PADRAO)


def _foto_fake_bytes(largura=640, altura=480):
    imagem = Image.new('RGB', (largura, altura), color=(120, 140, 160))
    saida = io.BytesIO()
    imagem.save(saida, format='JPEG')
    return saida.getvalue()


class ImageOverlayTests(TestCase):
    def _anuncio_fake(self, **overrides):
        dados = {
            'marca': 'Toyota',
            'modelo': 'Corolla XEI',
            'ano': '2022',
            'preco': Decimal('98500.00'),
        }
        dados.update(overrides)
        return SimpleNamespace(**dados)

    def test_monta_imagem_com_sucesso(self):
        imagem_bytes, mime_type = image_overlay.montar_imagem_overlay(
            _foto_fake_bytes(), self._anuncio_fake(), 'OPORTUNIDADE ÚNICA',
        )

        self.assertEqual(mime_type, 'image/jpeg')
        # Confere que o resultado e um JPEG valido, quadrado, no tamanho esperado.
        resultado = Image.open(io.BytesIO(imagem_bytes))
        self.assertEqual(resultado.format, 'JPEG')
        self.assertEqual(resultado.size, image_overlay.TAMANHO_SAIDA)

    def test_foto_invalida_levanta_image_overlay_error(self):
        with self.assertRaises(image_overlay.ImageOverlayError):
            image_overlay.montar_imagem_overlay(b'isso nao e uma imagem', self._anuncio_fake(), 'chamada')

    def test_preco_ausente_nao_quebra(self):
        # anuncio sem preco definido (None) - comum em veiculos "consulte o valor".
        imagem_bytes, _ = image_overlay.montar_imagem_overlay(
            _foto_fake_bytes(), self._anuncio_fake(preco=None), 'chamada',
        )
        self.assertTrue(imagem_bytes)

    def test_titulo_longo_nao_quebra(self):
        # marca/modelo bem longos, pra conferir que a quebra de linha nao estoura.
        imagem_bytes, _ = image_overlay.montar_imagem_overlay(
            _foto_fake_bytes(),
            self._anuncio_fake(modelo='Cross Sahara Diesel Automático 4x4 Top de Linha Completo'),
            'UMA CHAMADA BEM LONGA PRA TESTAR A QUEBRA DE LINHA TAMBEM',
        )
        self.assertTrue(imagem_bytes)


class GerarChamadaIaTests(TestCase):
    @patch('marketing_ia.ai_promocional.get_gemini_runtime')
    def test_usa_texto_da_ia_quando_disponivel(self, mock_runtime):
        client = Mock()
        client.models.generate_content.return_value = Mock(text=' "SAIU MAIS BARATO" ')
        mock_runtime.return_value = (client, 'gemini-2.5-flash', None)

        chamada = ai_promocional.gerar_chamada_ia(SimpleNamespace(
            titulo='Corolla 2022', marca='Toyota', modelo='Corolla', ano='2022',
            km='30000', cor='Prata', preco=Decimal('98500'), condicoes=[],
        ))

        self.assertEqual(chamada, 'SAIU MAIS BARATO')

    @patch('marketing_ia.ai_promocional.get_gemini_runtime')
    def test_cai_pro_fallback_quando_gemini_indisponivel(self, mock_runtime):
        mock_runtime.return_value = (None, None, 'sem chave configurada')

        chamada = ai_promocional.gerar_chamada_ia(SimpleNamespace(
            titulo='Corolla 2022', marca='Toyota', modelo='Corolla', ano='2022',
            km='30000', cor='Prata', preco=Decimal('98500'), condicoes=[],
        ))

        self.assertEqual(chamada, ai_promocional.CHAMADA_FALLBACK)
