from django.conf import settings
from minio_storage.storage import MinioMediaStorage
from urllib.parse import urljoin
from whitenoise.storage import CompressedManifestStaticFilesStorage

class PublicMediaStorage(MinioMediaStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def url(self, name):
        base_url = f'http{"s" if settings.MINIO_STORAGE_USE_HTTPS else ""}://{settings.MINIO_EXTERNAL_ENDPOINT}/'
        return urljoin(base_url, f'{self.bucket_name}/{name}')


class LenientManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Igual ao CompressedManifestStaticFilesStorage do WhiteNoise, mas nao derruba a
    pagina inteira com 500 se algum arquivo ficar de fora do manifest (ex: falha
    pontual de post-processing no collectstatic). Nesse caso, {% static %} cai para
    a URL sem hash daquele arquivo especifico, em vez de levantar excecao.
    `manifest_strict` e atributo de classe (nao aceito via kwargs no __init__), por
    isso a subclasse em vez de configurar direto pelas OPTIONS do STORAGES.
    """
    manifest_strict = False