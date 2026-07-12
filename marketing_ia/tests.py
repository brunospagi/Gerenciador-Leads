import base64
import io
import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from . import ai_promocional
from . import image_overlay
from . import leonardo_client
from . import openai_client
from . import scraping
from . import services
from .models import LayoutOverlay, PostPromocional, PreviewPost, VeiculoAnuncio

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


class DerivarFlagsCondicoesTests(TestCase):
    def test_detecta_ipva_pago_e_aceita_troca(self):
        ipva_pago, aceita_troca = scraping._derivar_flags_condicoes(['Aceita Troca', 'IPVA Pago'])
        self.assertTrue(ipva_pago)
        self.assertTrue(aceita_troca)

    def test_condicoes_sem_essas_tags_nao_marca_nada(self):
        ipva_pago, aceita_troca = scraping._derivar_flags_condicoes(['Único Dono', 'Revisões em dia'])
        self.assertFalse(ipva_pago)
        self.assertFalse(aceita_troca)

    def test_lista_vazia_nao_quebra(self):
        ipva_pago, aceita_troca = scraping._derivar_flags_condicoes([])
        self.assertFalse(ipva_pago)
        self.assertFalse(aceita_troca)


class TituloVeiculoComMotorizacaoTests(TestCase):
    def test_inclui_motorizacao_quando_presente(self):
        anuncio = SimpleNamespace(marca='Fiat', modelo='Palio', ano='2012', motorizacao='1.0')
        titulo = image_overlay._titulo_veiculo(anuncio)
        self.assertEqual(titulo, 'FIAT PALIO 1.0 2012')

    def test_sem_motorizacao_nao_quebra(self):
        anuncio = SimpleNamespace(marca='Fiat', modelo='Palio', ano='2012', motorizacao=None)
        titulo = image_overlay._titulo_veiculo(anuncio)
        self.assertEqual(titulo, 'FIAT PALIO 2012')

    def test_sem_atributo_motorizacao_nao_quebra(self):
        # SimpleNamespace sem o atributo (simula um objeto que nunca passou por
        # getattr) -- _titulo_veiculo usa getattr(..., None) por causa disso.
        anuncio = SimpleNamespace(marca='Fiat', modelo='Palio', ano='2012')
        titulo = image_overlay._titulo_veiculo(anuncio)
        self.assertEqual(titulo, 'FIAT PALIO 2012')


class DadosVeiculoParaPromptTests(TestCase):
    def _anuncio(self, **overrides):
        dados = dict(
            titulo='Fiat Palio 2012', marca='Fiat', modelo='Palio', ano='2012', km='50000',
            cor='Branco', preco=Decimal('26900'), condicoes=[], ipva_pago=False, aceita_troca=False,
        )
        dados.update(overrides)
        return SimpleNamespace(**dados)

    def test_flags_geram_vantagens_reformulaveis_sem_citar_a_tag_crua(self):
        anuncio = self._anuncio(ipva_pago=True, aceita_troca=True, condicoes=['IPVA Pago', 'Aceita Troca'])
        prompt = ai_promocional._dados_veiculo_para_prompt(anuncio)
        self.assertIn('Vantagens: IPVA pago, Aceita troca', prompt)

    def test_outras_condicoes_nao_relacionadas_sao_preservadas(self):
        anuncio = self._anuncio(condicoes=['Único Dono'])
        prompt = ai_promocional._dados_veiculo_para_prompt(anuncio)
        self.assertIn('Vantagens: Único Dono', prompt)

    def test_sem_vantagens_nao_inclui_a_linha(self):
        anuncio = self._anuncio()
        prompt = ai_promocional._dados_veiculo_para_prompt(anuncio)
        self.assertNotIn('Vantagens:', prompt)


class VeiculoListFiltroVantagensTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin_vant', 'admin_vant@teste.com', 'senha12345')
        self.client.login(username='admin_vant', password='senha12345')
        self.com_ipva = _anuncio_persistido(external_id='ipva-1', ipva_pago=True, aceita_troca=False)
        self.sem_flags = _anuncio_persistido(external_id='sem-flags-1', ipva_pago=False, aceita_troca=False)

    def test_filtro_ipva_pago_na_listagem(self):
        resp = self.client.get(reverse('marketing_veiculo_list'), {'ipva_pago': '1'})
        veiculos = list(resp.context['veiculos'])
        self.assertIn(self.com_ipva, veiculos)
        self.assertNotIn(self.sem_flags, veiculos)

    def test_lote_respeita_filtro_de_vantagem(self):
        resp = self.client.post(reverse('marketing_iniciar_lote'), {'ipva_pago': '1'})
        self.assertEqual(resp.status_code, 302)
        from .models import LoteGeracao
        lote = LoteGeracao.objects.latest('criado_em')
        self.assertEqual(lote.alvo_ids, [self.com_ipva.pk])


class MontarImagemLayoutTests(TestCase):
    def _anuncio_fake(self, **overrides):
        dados = {'marca': 'Toyota', 'modelo': 'Corolla', 'ano': '2022', 'preco': Decimal('98500.00')}
        dados.update(overrides)
        return SimpleNamespace(**dados)

    def test_renderiza_forma_texto_e_logo(self):
        elementos = [
            {'tipo': 'forma', 'x': 0, 'y': 0.7, 'largura': 1, 'altura': 0.3,
             'cor_fundo': '#0f172a', 'opacidade': 0.9, 'arredondado': 0},
            {'tipo': 'texto', 'campo': 'titulo', 'x': 0.06, 'y': 0.75, 'largura': 0.8,
             'tamanho_fonte': 0.05, 'cor_texto': '#ffffff', 'alinhamento': 'esquerda'},
            {'tipo': 'texto', 'campo': 'preco', 'x': 0.06, 'y': 0.85, 'largura': 0.8,
             'tamanho_fonte': 0.06, 'cor_texto': '#4ade80'},
            {'tipo': 'texto', 'campo': 'fixo', 'texto_fixo': 'Vem com garantia', 'x': 0.06, 'y': 0.05, 'largura': 0.5},
            {'tipo': 'logo', 'x': 0.75, 'y': 0.72, 'altura': 0.08},
        ]

        imagem_bytes, mime_type = image_overlay.montar_imagem_layout(
            _foto_fake_bytes(), self._anuncio_fake(), 'SUPER OFERTA', elementos,
        )

        self.assertEqual(mime_type, 'image/jpeg')
        resultado = Image.open(io.BytesIO(imagem_bytes))
        self.assertEqual(resultado.format, 'JPEG')
        self.assertEqual(resultado.size, image_overlay.RESOLUCOES[image_overlay.RESOLUCAO_PADRAO])

    def test_elemento_invalido_e_pulado_sem_quebrar(self):
        elementos = [
            {'tipo': 'forma', 'x': 0, 'y': 0, 'largura': 'nao-e-numero', 'altura': 0.1},
            {'tipo': 'texto', 'campo': 'titulo', 'x': 0.1, 'y': 0.1, 'largura': 0.5},
        ]
        imagem_bytes, _ = image_overlay.montar_imagem_layout(
            _foto_fake_bytes(), self._anuncio_fake(), 'chamada', elementos,
        )
        self.assertTrue(imagem_bytes)

    def test_lista_vazia_gera_so_a_foto(self):
        imagem_bytes, mime_type = image_overlay.montar_imagem_layout(
            _foto_fake_bytes(), self._anuncio_fake(), 'chamada', [],
        )
        self.assertEqual(mime_type, 'image/jpeg')
        self.assertTrue(imagem_bytes)

    def test_todas_as_resolucoes_funcionam(self):
        elemento = [{'tipo': 'texto', 'campo': 'preco', 'x': 0.1, 'y': 0.1, 'largura': 0.5}]
        for chave, tamanho in image_overlay.RESOLUCOES.items():
            imagem_bytes, _ = image_overlay.montar_imagem_layout(
                _foto_fake_bytes(), self._anuncio_fake(), 'chamada', elemento, resolucao=chave,
            )
            resultado = Image.open(io.BytesIO(imagem_bytes))
            self.assertEqual(resultado.size, tamanho)


class LayoutOverlayModelTests(TestCase):
    def test_chave_template_usa_prefixo_custom(self):
        layout = LayoutOverlay.objects.create(nome='Meu layout', elementos=[])
        self.assertEqual(layout.chave_template, f'CUSTOM:{layout.pk}')


class GerarImagemOverlayComLayoutCustomTests(TestCase):
    def _anuncio(self, **overrides):
        dados = dict(
            external_id='ext-layout-1', url='https://spagimotors.com.br/x', tipo='CARRO',
            marca='Toyota', modelo='Corolla', titulo='Toyota Corolla 2022', preco=Decimal('98500'),
            fotos_urls=['https://cdn.exemplo.com/foto.jpg'], foto_principal_url='https://cdn.exemplo.com/foto.jpg',
        )
        dados.update(overrides)
        return VeiculoAnuncio.objects.create(**dados)

    @patch('marketing_ia.ai_promocional.gerar_chamada_ia', return_value='SUPER OFERTA')
    def test_usa_layout_customizado_quando_prefixo_custom(self, mock_chamada):
        layout = LayoutOverlay.objects.create(nome='Layout teste', elementos=[
            {'tipo': 'texto', 'campo': 'preco', 'x': 0.1, 'y': 0.8, 'largura': 0.6},
        ])
        anuncio = self._anuncio()

        imagem_bytes, mime_type, modelo, chamada = ai_promocional._gerar_imagem_overlay(
            anuncio, _foto_fake_bytes(), 'image/jpeg', template_overlay=layout.chave_template,
        )

        self.assertTrue(imagem_bytes)
        self.assertEqual(mime_type, 'image/jpeg')
        self.assertIn(f'custom:{layout.pk}', modelo)

    @patch('marketing_ia.ai_promocional.gerar_chamada_ia', return_value='SUPER OFERTA')
    def test_layout_inexistente_cai_pro_padrao(self, mock_chamada):
        anuncio = self._anuncio(external_id='ext-layout-2')

        imagem_bytes, mime_type, modelo, chamada = ai_promocional._gerar_imagem_overlay(
            anuncio, _foto_fake_bytes(), 'image/jpeg', template_overlay='CUSTOM:99999',
        )

        self.assertTrue(imagem_bytes)
        self.assertIn(image_overlay.TEMPLATE_PADRAO, modelo)


class LayoutEditorViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin_layout', 'admin_layout@teste.com', 'senha12345')
        self.client.login(username='admin_layout', password='senha12345')

    def test_layout_list_carrega(self):
        resp = self.client.get(reverse('marketing_layout_list'))
        self.assertEqual(resp.status_code, 200)

    def test_editor_novo_sem_base_comeca_vazio(self):
        resp = self.client.get(reverse('marketing_layout_novo'))
        self.assertEqual(resp.status_code, 200)

    def test_editor_novo_com_base_clona_elementos_do_template_fixo(self):
        resp = self.client.get(reverse('marketing_layout_novo'), {'base': 'FAIXA_INFERIOR'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'cor_fundo', resp.content)

    def test_salvar_cria_novo_layout(self):
        resp = self.client.post(
            reverse('marketing_layout_salvar'),
            data=json.dumps({'nome': 'Meu novo layout', 'elementos': [{'tipo': 'logo', 'x': 0.1, 'y': 0.1, 'altura': 0.05}]}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertTrue(LayoutOverlay.objects.filter(pk=data['pk']).exists())

    def test_salvar_sem_nome_retorna_erro(self):
        resp = self.client.post(
            reverse('marketing_layout_salvar'),
            data=json.dumps({'nome': '', 'elementos': []}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['ok'])

    def test_atualizar_layout_existente(self):
        layout = LayoutOverlay.objects.create(nome='Original', elementos=[])
        resp = self.client.post(
            reverse('marketing_layout_atualizar', args=[layout.pk]),
            data=json.dumps({
                'nome': 'Renomeado',
                'elementos': [{'tipo': 'forma', 'x': 0, 'y': 0, 'largura': 0.5, 'altura': 0.5}],
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        layout.refresh_from_db()
        self.assertEqual(layout.nome, 'Renomeado')
        self.assertEqual(len(layout.elementos), 1)

    def test_excluir_layout(self):
        layout = LayoutOverlay.objects.create(nome='Pra excluir', elementos=[])
        resp = self.client.post(reverse('marketing_layout_excluir', args=[layout.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(LayoutOverlay.objects.filter(pk=layout.pk).exists())

    def test_preview_sem_anuncio_usa_foto_sintetica(self):
        resp = self.client.post(
            reverse('marketing_layout_preview'),
            data=json.dumps({
                'elementos': [{'tipo': 'texto', 'campo': 'preco', 'x': 0.1, 'y': 0.8, 'largura': 0.6}],
                'resolucao': '1080x1080',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/jpeg')

    def test_preview_com_elementos_invalidos_retorna_400(self):
        resp = self.client.post(
            reverse('marketing_layout_preview'),
            data=json.dumps({'elementos': 'nao-e-uma-lista'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)


class DerivarVeiculoCompletoTests(TestCase):
    def test_detecta_completo_com_os_tres_opcionais(self):
        self.assertTrue(scraping._derivar_veiculo_completo(
            ['Ar Condicionado', 'Direção Hidráulica', 'Vidros Elétricos'],
        ))

    def test_variacoes_de_grafia_tambem_contam(self):
        self.assertTrue(scraping._derivar_veiculo_completo(
            ['ar-condicionado', 'direcao eletrica', 'vidro eletrico'],
        ))

    def test_faltando_um_opcional_nao_marca_completo(self):
        self.assertFalse(scraping._derivar_veiculo_completo(['Ar Condicionado', 'Direção Hidráulica']))

    def test_lista_vazia_nao_marca_completo(self):
        self.assertFalse(scraping._derivar_veiculo_completo([]))


class TextoElementoCamposNovosTests(TestCase):
    def _anuncio(self, **overrides):
        dados = {'marca': 'Toyota', 'modelo': 'Corolla', 'ano': '2022', 'preco': Decimal('98500'),
                 'opcionais': ['Ar condicionado', 'Airbag', 'ABS', 'Vidro elétrico', 'Trava elétrica'],
                 'veiculo_completo': True}
        dados.update(overrides)
        return SimpleNamespace(**dados)

    def test_campo_opcionais_junta_so_os_4_primeiros(self):
        elemento = {'campo': 'opcionais', 'maiusculas': False}
        texto = image_overlay._texto_do_elemento(elemento, self._anuncio(), 'chamada')
        self.assertEqual(texto, 'Ar condicionado, Airbag, ABS, Vidro elétrico')

    def test_campo_veiculo_completo_mostra_texto_quando_marcado(self):
        elemento = {'campo': 'veiculo_completo', 'maiusculas': False}
        texto = image_overlay._texto_do_elemento(elemento, self._anuncio(veiculo_completo=True), 'chamada')
        self.assertEqual(texto, 'Veículo Completo')

    def test_campo_veiculo_completo_vazio_quando_nao_marcado(self):
        elemento = {'campo': 'veiculo_completo', 'maiusculas': False}
        texto = image_overlay._texto_do_elemento(elemento, self._anuncio(veiculo_completo=False), 'chamada')
        self.assertEqual(texto, '')


class DesenharElementoFormaCirculoTests(TestCase):
    def test_forma_circulo_nao_quebra_e_gera_imagem_valida(self):
        elementos = [
            {'tipo': 'forma', 'formato': 'circulo', 'x': 0.1, 'y': 0.1, 'largura': 0.2, 'altura': 0.2, 'cor_fundo': '#c52b30'},
        ]
        anuncio = SimpleNamespace(marca='Fiat', modelo='Palio', ano='2012', preco=Decimal('26900'))
        imagem_bytes, mime_type = image_overlay.montar_imagem_layout(_foto_fake_bytes(), anuncio, 'chamada', elementos)
        self.assertEqual(mime_type, 'image/jpeg')
        self.assertTrue(imagem_bytes)


class DesenharElementoEmojiTests(TestCase):
    def test_emoji_e_desenhado_sem_quebrar(self):
        elementos = [{'tipo': 'emoji', 'emoji': '🔥', 'x': 0.1, 'y': 0.1, 'altura': 0.1}]
        anuncio = SimpleNamespace(marca='Fiat', modelo='Palio', ano='2012', preco=Decimal('26900'))
        imagem_bytes, mime_type = image_overlay.montar_imagem_layout(_foto_fake_bytes(), anuncio, 'chamada', elementos)
        self.assertEqual(mime_type, 'image/jpeg')
        self.assertTrue(imagem_bytes)

    def test_emoji_vazio_e_ignorado(self):
        elementos = [{'tipo': 'emoji', 'emoji': '', 'x': 0.1, 'y': 0.1, 'altura': 0.1}]
        anuncio = SimpleNamespace(marca='Fiat', modelo='Palio', ano='2012', preco=Decimal('26900'))
        imagem_bytes, _ = image_overlay.montar_imagem_layout(_foto_fake_bytes(), anuncio, 'chamada', elementos)
        self.assertTrue(imagem_bytes)


class FonteComAcentuacaoTests(TestCase):
    def test_fonte_padrao_nao_e_mais_o_default_do_pillow_sem_acento(self):
        # regressão do bug: ImageFont.load_default() (fonte Aileron embutida do
        # Pillow) não tem glifos de á/ã/ç/õ etc — troquei pra Poppins (arquivo
        # de verdade em static/fonts/), que tem cobertura completa de Latin Extended.
        fonte = image_overlay._fonte(40)
        self.assertNotEqual(fonte.getname()[0], 'Aileron')

    def test_todas_as_fontes_do_editor_carregam_sem_erro(self):
        for chave, _ in image_overlay.FONTE_CHOICES:
            fonte = image_overlay._fonte(40, chave)
            self.assertIsNotNone(fonte)


class SincronizacaoTimeoutTests(TestCase):
    def test_sincronizacao_travada_por_muito_tempo_e_marcada_como_erro(self):
        
        from marketing_ia.models import SincronizacaoEstoque
        sync = SincronizacaoEstoque.load()
        sync.status = 'RODANDO'
        sync.iniciado_em = timezone.now() - timedelta(minutes=SincronizacaoEstoque.TIMEOUT_MINUTOS + 5)
        sync.save()

        sync_recarregada = SincronizacaoEstoque.load()

        self.assertEqual(sync_recarregada.status, 'ERRO')
        self.assertIn('interrompida', sync_recarregada.resultado)

    def test_sincronizacao_recente_nao_e_afetada(self):
        
        from marketing_ia.models import SincronizacaoEstoque
        sync = SincronizacaoEstoque.load()
        sync.status = 'RODANDO'
        sync.iniciado_em = timezone.now() - timedelta(minutes=2)
        sync.save()

        sync_recarregada = SincronizacaoEstoque.load()

        self.assertEqual(sync_recarregada.status, 'RODANDO')


class CancelarSincronizacaoViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin_sync', 'admin_sync@teste.com', 'senha12345')
        self.client.login(username='admin_sync', password='senha12345')

    def test_cancela_sincronizacao_rodando(self):
        from marketing_ia.models import SincronizacaoEstoque
        sync = SincronizacaoEstoque.load()
        sync.status = 'RODANDO'
        sync.iniciado_em = timezone.now()
        sync.save()

        resp = self.client.post(reverse('marketing_cancelar_sincronizacao'))

        self.assertEqual(resp.status_code, 302)
        sync.refresh_from_db()
        self.assertEqual(sync.status, 'ERRO')

    def test_nao_faz_nada_se_nao_estiver_rodando(self):
        from marketing_ia.models import SincronizacaoEstoque
        sync = SincronizacaoEstoque.load()
        self.assertEqual(sync.status, 'OCIOSO')

        resp = self.client.post(reverse('marketing_cancelar_sincronizacao'))

        self.assertEqual(resp.status_code, 302)
        sync.refresh_from_db()
        self.assertEqual(sync.status, 'OCIOSO')


class ContarLoteViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin_contar', 'admin_contar@teste.com', 'senha12345')
        self.client.login(username='admin_contar', password='senha12345')
        _anuncio_persistido(external_id='completo-1', veiculo_completo=True)
        _anuncio_persistido(external_id='incompleto-1', veiculo_completo=False)

    def test_conta_apenas_veiculo_completo_quando_filtrado(self):
        resp = self.client.get(reverse('marketing_contar_lote'), {'veiculo_completo': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total'], 1)

    def test_conta_todos_sem_post_sem_filtro(self):
        resp = self.client.get(reverse('marketing_contar_lote'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total'], 2)
