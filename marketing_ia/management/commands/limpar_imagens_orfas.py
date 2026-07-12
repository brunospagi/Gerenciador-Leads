from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from marketing_ia.models import PostPromocional

PREFIXO_POSTS = 'marketing_ia/posts'


def _listar_arquivos_recursivo(caminho):
    """default_storage.listdir só lista um nível — as imagens ficam em
    subpastas por external_id (marketing_ia/posts/<external_id>/<arquivo>),
    por isso precisa descer recursivamente."""
    diretorios, arquivos = default_storage.listdir(caminho)
    caminhos = [f'{caminho}/{arquivo}' for arquivo in arquivos]
    for subdiretorio in diretorios:
        caminhos.extend(_listar_arquivos_recursivo(f'{caminho}/{subdiretorio}'))
    return caminhos


class Command(BaseCommand):
    help = (
        'Localiza e remove arquivos "órfãos" no bucket do MinIO/S3 dentro de '
        f'{PREFIXO_POSTS}/ — imagens que sobraram de posts excluídos direto no '
        'banco (ex: via admin) e nunca foram apagadas do storage. Por padrão só '
        'lista o que seria removido; use --apagar para de fato remover.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apagar', action='store_true',
                             help='Remove de fato os arquivos órfãos encontrados (padrão: só lista, dry-run).')

    def handle(self, *args, **options):
        try:
            arquivos_no_storage = set(_listar_arquivos_recursivo(PREFIXO_POSTS))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING(f'Pasta "{PREFIXO_POSTS}" ainda não existe no storage.'))
            return

        arquivos_em_uso = set(
            PostPromocional.objects.exclude(imagem='').values_list('imagem', flat=True)
        )

        orfaos = sorted(arquivos_no_storage - arquivos_em_uso)

        if not orfaos:
            self.stdout.write(self.style.SUCCESS('Nenhum arquivo órfão encontrado.'))
            return

        self.stdout.write(f'{len(orfaos)} arquivo(s) órfão(s) encontrado(s) em "{PREFIXO_POSTS}/":')
        for caminho in orfaos:
            self.stdout.write(f'  - {caminho}')

        if not options['apagar']:
            self.stdout.write(self.style.WARNING(
                'Nenhum arquivo foi removido (dry-run). Rode de novo com --apagar para remover.'
            ))
            return

        removidos = 0
        for caminho in orfaos:
            try:
                default_storage.delete(caminho)
                removidos += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'Falha ao apagar "{caminho}": {exc}'))

        self.stdout.write(self.style.SUCCESS(f'{removidos} arquivo(s) órfão(s) removido(s).'))
