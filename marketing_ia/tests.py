import base64
import io
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from . import ai_promocional
from . import image_overlay
from . import leonardo_client
from . import openai_client
from . import services
from .models import PostPromocional, PreviewPost, VeiculoAnuncio

User = get_user_model()


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
        # Confere que o resultado e um JPEG valido, no tamanho esperado (resolucao padrao).
        resultado = Image.open(io.BytesIO(imagem_bytes))
        self.assertEqual(resultado.format, 'JPEG')
        self.assertEqual(resultado.size, image_overlay.RESOLUCOES[image_overlay.RESOLUCAO_PADRAO])

    def test_todos_os_templates_geram_imagem_valida(self):
        for template in image_overlay._TEMPLATES:
            imagem_bytes, mime_type = image_overlay.montar_imagem_overlay(
                _foto_fake_bytes(), self._anuncio_fake(), 'OPORTUNIDADE ÚNICA', template=template,
            )
            self.assertEqual(mime_type, 'image/jpeg')
            resultado = Image.open(io.BytesIO(imagem_bytes))
            self.assertEqual(resultado.format, 'JPEG')

    def test_todas_as_resolucoes_geram_tamanho_correto(self):
        for chave, tamanho in image_overlay.RESOLUCOES.items():
            imagem_bytes, _ = image_overlay.montar_imagem_overlay(
                _foto_fake_bytes(), self._anuncio_fake(), 'OPORTUNIDADE ÚNICA', resolucao=chave,
            )
            resultado = Image.open(io.BytesIO(imagem_bytes))
            self.assertEqual(resultado.size, tamanho)

    def test_template_invalido_cai_para_padrao(self):
        imagem_bytes, _ = image_overlay.montar_imagem_overlay(
            _foto_fake_bytes(), self._anuncio_fake(), 'chamada', template='NAO_EXISTE',
        )
        self.assertTrue(imagem_bytes)

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


def _anuncio_persistido(**overrides):
    dados = {
        'external_id': 'ext-1',
        'url': 'https://spagimotors.com.br/veiculo/1',
        'tipo': 'CARRO',
        'marca': 'Toyota',
        'modelo': 'Corolla',
        'titulo': 'Toyota Corolla XEI 2022',
        'preco': Decimal('98500.00'),
        'foto_principal_url': 'https://cdn.spagimotors.com.br/foto1.jpg',
        'fotos_urls': ['https://cdn.spagimotors.com.br/foto1.jpg'],
    }
    dados.update(overrides)
    return VeiculoAnuncio.objects.create(**dados)


class PreviewPostServiceTests(TestCase):
    """Prévia deve gravar só no banco (PreviewPost.imagem_bytes), nunca no S3,
    até ser explicitamente confirmada — é o requisito central do fluxo."""

    def setUp(self):
        self.anuncio = _anuncio_persistido()

    @patch('marketing_ia.services.gerar_legenda')
    @patch('marketing_ia.services.gerar_imagem_promocional')
    @patch('marketing_ia.services.baixar_foto')
    def test_gerar_preview_post_nao_grava_no_storage(self, mock_baixar, mock_gerar_imagem, mock_legenda):
        mock_baixar.return_value = (b'foto-fake', 'image/jpeg')
        mock_gerar_imagem.return_value = (b'imagem-gerada', 'image/jpeg', 'overlay:pillow', 'prompt-x')
        mock_legenda.return_value = ('Legenda de teste', '#carro #oferta', 'gemini-2.5-flash')

        with patch('crmspagi.storage_backends.MinioMediaStorage._save') as mock_save:
            preview = services.gerar_preview_post(self.anuncio, usuario=None)
            mock_save.assert_not_called()

        self.assertEqual(bytes(preview.imagem_bytes), b'imagem-gerada')
        self.assertEqual(preview.legenda, 'Legenda de teste')
        self.assertEqual(PreviewPost.objects.count(), 1)
        self.assertEqual(PostPromocional.objects.count(), 0)

    @patch('marketing_ia.services.gerar_legenda')
    @patch('marketing_ia.services.gerar_imagem_promocional')
    @patch('marketing_ia.services.baixar_foto')
    def test_gerar_preview_post_sem_fotos_levanta_erro(self, mock_baixar, mock_gerar_imagem, mock_legenda):
        anuncio_sem_foto = _anuncio_persistido(external_id='ext-2', fotos_urls=[], foto_principal_url='')
        with self.assertRaises(services.GeracaoPostError):
            services.gerar_preview_post(anuncio_sem_foto)
        mock_baixar.assert_not_called()

    def test_confirmar_preview_grava_post_e_apaga_previa(self):
        preview = PreviewPost.objects.create(
            anuncio=self.anuncio,
            imagem_bytes=b'imagem-gerada',
            imagem_mime_type='image/jpeg',
            legenda='Legenda de teste',
            hashtags='#carro',
            modelo_ia_imagem='overlay:pillow',
        )

        with patch('crmspagi.storage_backends.MinioMediaStorage._save', return_value='marketing_ia/posts/ext-1/post.jpg') as mock_save:
            post = services.salvar_preview_como_post(preview)
            mock_save.assert_called_once()

        self.assertEqual(PostPromocional.objects.count(), 1)
        self.assertEqual(PreviewPost.objects.count(), 0)
        self.assertEqual(post.legenda, 'Legenda de teste')
        self.assertEqual(post.anuncio_id, self.anuncio.pk)


class PreviewPostViewTests(TestCase):
    def setUp(self):
        self.anuncio = _anuncio_persistido()
        self.user = User.objects.create_superuser('admin_preview', 'admin_preview@teste.com', 'senha12345')
        self.client.login(username='admin_preview', password='senha12345')

    @patch('marketing_ia.views.gerar_preview_post')
    def test_gerar_preview_view_retorna_json_com_url_da_imagem(self, mock_gerar_preview):
        preview_fake = SimpleNamespace(
            pk=42, legenda='Legenda', hashtags='#tag', modelo_ia_imagem='overlay:pillow',
        )
        mock_gerar_preview.return_value = preview_fake

        resp = self.client.post(reverse('marketing_gerar_preview', args=[self.anuncio.pk]))

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['preview_id'], 42)
        self.assertIn('/preview/42/imagem/', data['imagem_url'])

    @patch('marketing_ia.views.gerar_preview_post')
    def test_gerar_preview_view_com_erro_esperado_retorna_400(self, mock_gerar_preview):
        mock_gerar_preview.side_effect = services.GeracaoPostError('sem fotos')

        resp = self.client.post(reverse('marketing_gerar_preview', args=[self.anuncio.pk]))

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['ok'])

    def test_preview_imagem_serve_os_bytes_gravados(self):
        preview = PreviewPost.objects.create(
            anuncio=self.anuncio, imagem_bytes=b'bytes-da-imagem', imagem_mime_type='image/jpeg',
        )

        resp = self.client.get(reverse('marketing_preview_imagem', args=[preview.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'bytes-da-imagem')
        self.assertEqual(resp['Content-Type'], 'image/jpeg')

    def test_descartar_preview_apaga_sem_criar_post(self):
        preview = PreviewPost.objects.create(
            anuncio=self.anuncio, imagem_bytes=b'bytes', imagem_mime_type='image/jpeg',
        )

        self.client.post(reverse('marketing_descartar_preview', args=[preview.pk]))

        self.assertEqual(PreviewPost.objects.count(), 0)
        self.assertEqual(PostPromocional.objects.count(), 0)

    def test_confirmar_preview_grava_post_via_view(self):
        preview = PreviewPost.objects.create(
            anuncio=self.anuncio, imagem_bytes=b'bytes', imagem_mime_type='image/jpeg', legenda='Legenda',
        )

        with patch('crmspagi.storage_backends.MinioMediaStorage._save', return_value='marketing_ia/posts/ext-1/post.jpg'):
            resp = self.client.post(reverse('marketing_confirmar_preview', args=[preview.pk]))

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(PreviewPost.objects.count(), 0)
        self.assertEqual(PostPromocional.objects.count(), 1)


class LimparImagensOrfasCommandTests(TestCase):
    def setUp(self):
        self.anuncio = _anuncio_persistido()

    @patch('marketing_ia.management.commands.limpar_imagens_orfas.default_storage')
    def test_lista_orfaos_sem_apagar_por_padrao(self, mock_storage):
        PostPromocional.objects.create(
            anuncio=self.anuncio,
            imagem='marketing_ia/posts/ext-1/em-uso.jpg',
            legenda='Legenda',
        )

        def listdir_side_effect(caminho):
            if caminho == 'marketing_ia/posts':
                return (['ext-1'], [])
            if caminho == 'marketing_ia/posts/ext-1':
                return ([], ['em-uso.jpg', 'orfao.jpg'])
            return ([], [])

        mock_storage.listdir.side_effect = listdir_side_effect

        out = io.StringIO()
        call_command('limpar_imagens_orfas', stdout=out)

        saida = out.getvalue()
        self.assertIn('orfao.jpg', saida)
        self.assertNotIn('em-uso.jpg', saida.split('encontrado(s) em')[-1] if 'encontrado(s) em' in saida else '')
        mock_storage.delete.assert_not_called()

    @patch('marketing_ia.management.commands.limpar_imagens_orfas.default_storage')
    def test_apaga_orfaos_quando_flag_passada(self, mock_storage):
        def listdir_side_effect(caminho):
            if caminho == 'marketing_ia/posts':
                return ([], ['orfao.jpg'])
            return ([], [])

        mock_storage.listdir.side_effect = listdir_side_effect

        out = io.StringIO()
        call_command('limpar_imagens_orfas', '--apagar', stdout=out)

        mock_storage.delete.assert_called_once_with('marketing_ia/posts/orfao.jpg')

    @patch('marketing_ia.management.commands.limpar_imagens_orfas.default_storage')
    def test_sem_orfaos_nao_chama_delete(self, mock_storage):
        PostPromocional.objects.create(
            anuncio=self.anuncio,
            imagem='marketing_ia/posts/ext-1/em-uso.jpg',
            legenda='Legenda',
        )

        def listdir_side_effect(caminho):
            if caminho == 'marketing_ia/posts':
                return (['ext-1'], [])
            if caminho == 'marketing_ia/posts/ext-1':
                return ([], ['em-uso.jpg'])
            return ([], [])

        mock_storage.listdir.side_effect = listdir_side_effect

        out = io.StringIO()
        call_command('limpar_imagens_orfas', stdout=out)

        self.assertIn('Nenhum arquivo órfão', out.getvalue())
        mock_storage.delete.assert_not_called()
