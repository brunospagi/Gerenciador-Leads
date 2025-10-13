from django.conf import settings
from minio_storage.storage import MinioMediaStorage
from urllib.parse import urljoin

class PublicMediaStorage(MinioMediaStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def url(self, name):
        print(f"!!! PublicMediaStorage.url FOI CHAMADO PARA O FICHEIRO: {name} !!!") # <-- Adicione esta linha
        base_url = f'http{"s" if settings.MINIO_STORAGE_USE_HTTPS else ""}://{settings.MINIO_EXTERNAL_ENDPOINT}/'
        return urljoin(base_url, f'{self.bucket_name}/{name}')