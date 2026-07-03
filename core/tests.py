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
            'whitenoise.storage.CompressedManifestStaticFilesStorage',
        )
        # Confirma que a storage configurada tem post_process (so existe em storages
        # com hashing/manifest; a StaticFilesStorage simples do Django nao tem).
        self.assertTrue(hasattr(staticfiles_storage, 'post_process'))
