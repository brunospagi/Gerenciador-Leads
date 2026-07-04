from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import TestCase


class StorageConfigTests(TestCase):
    """
    Regressao: DEFAULT_FILE_STORAGE/STATICFILES_STORAGE (estilo antigo) foram removidos
    pelo Django a partir da 5.1 - definir so essas configuracoes faz o Django ignora-las
    silenciosamente e cair nos backends padrao (FileSystemStorage local / StaticFilesStorage
    sem hash), enviando uploads de usuario para o disco do container (perdidos a cada
    redeploy) em vez do MinIO, e quebrando o cache-busting dos arquivos estaticos.
    """

    def test_default_storage_usa_minio(self):
        self.assertEqual(
            settings.STORAGES['default']['BACKEND'],
            'crmspagi.storage_backends.PublicMediaStorage',
        )
        self.assertEqual(
            default_storage.__class__.__module__,
            'crmspagi.storage_backends',
        )

    def test_staticfiles_storage_usa_manifest_do_whitenoise(self):
        self.assertEqual(
            settings.STORAGES['staticfiles']['BACKEND'],
            'crmspagi.storage_backends.LenientManifestStaticFilesStorage',
        )
        # Confirma que a storage configurada tem post_process (so existe em storages
        # com hashing/manifest; a StaticFilesStorage simples do Django nao tem).
        self.assertTrue(hasattr(staticfiles_storage, 'post_process'))
        # manifest_strict=False: entrada ausente no manifest nao pode derrubar a pagina.
        self.assertFalse(staticfiles_storage.manifest_strict)

    def test_entrada_ausente_no_manifest_nao_derruba_static_tag(self):
        """
        Regressao do incidente de producao: 'ValueError: Missing staticfiles
        manifest entry for css/app_m3.css' derrubou a home com 500. Simula uma
        entrada ausente no manifest (para um arquivo que existe de verdade em
        static/) e confirma que a resolucao cai para o hash calculado na hora,
        em vez de lancar excecao.
        """
        nome = 'css/app_m3.css'
        hash_key = staticfiles_storage.hash_key(nome)
        original = staticfiles_storage.hashed_files.pop(hash_key, None)
        try:
            url = staticfiles_storage.url(nome)
            self.assertTrue(url.startswith('/static/css/app_m3'))
        finally:
            if original is not None:
                staticfiles_storage.hashed_files[hash_key] = original
