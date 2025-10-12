from django.conf import settings
from minio_storage.storage import MinioMediaStorage
from urllib.parse import urljoin

class PublicMediaStorage(MinioMediaStorage):
    """
    Esta classe de storage customizada herda do MinioMediaStorage
    mas força a geração de URLs usando o endpoint PÚBLICO definido
    em MINIO_EXTERNAL_ENDPOINT.
    """
    def url(self, name):
        # Monta a URL base a partir do endpoint externo (ex: http://s3.spagisistemas.com.br/)
        base_url = f'http{"s" if settings.MINIO_STORAGE_USE_HTTPS else ""}://{settings.MINIO_EXTERNAL_ENDPOINT}/'
        
        # Junta a URL base com o nome do bucket e o nome do arquivo
        # Resultado: http://s3.spagisistemas.com.br/media/caminho/para/arquivo.jpg
        return urljoin(base_url, f'{self.bucket_name}/{name}')