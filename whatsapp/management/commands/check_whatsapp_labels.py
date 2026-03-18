from django.core.management.base import BaseCommand

from whatsapp.services import reconcile_contact_labels


class Command(BaseCommand):
    help = 'Reconcilia labels/etiquetas dos contatos WhatsApp com as conversas locais.'

    def add_arguments(self, parser):
        parser.add_argument('--page-size', type=int, default=200, help='Quantidade de itens por pagina na Evolution API.')
        parser.add_argument('--max-pages', type=int, default=8, help='Quantidade maxima de paginas por execucao.')
        parser.add_argument('--clear-missing', action='store_true', help='Limpa etiquetas locais quando o contato remoto nao tiver labels.')
        parser.add_argument('--dry-run', action='store_true', help='Simula sem gravar no banco.')

    def handle(self, *args, **options):
        page_size = int(options.get('page_size') or 200)
        max_pages = int(options.get('max_pages') or 8)
        clear_missing = bool(options.get('clear_missing'))
        dry_run = bool(options.get('dry_run'))

        self.stdout.write(
            'Iniciando reconciliacao de etiquetas WhatsApp '
            f'(page_size={page_size}, max_pages={max_pages}, clear_missing={clear_missing}, dry_run={dry_run})...'
        )

        stats = reconcile_contact_labels(
            page_size=page_size,
            max_pages=max_pages,
            clear_missing=clear_missing,
            dry_run=dry_run,
        )

        self.stdout.write(
            self.style.SUCCESS(
                'Concluido. '
                f"checked={stats.get('checked', 0)} "
                f"matched={stats.get('matched', 0)} "
                f"updated={stats.get('updated', 0)} "
                f"labels_updated={stats.get('labels_updated', 0)} "
                f"name_updated={stats.get('name_updated', 0)} "
                f"avatar_updated={stats.get('avatar_updated', 0)} "
                f"cleared_labels={stats.get('cleared_labels', 0)} "
                f"no_conversation={stats.get('no_conversation', 0)} "
                f"pages={stats.get('pages', 0)} "
                f"api_errors={stats.get('api_errors', 0)} "
                f"no_instance={stats.get('no_instance', 0)}"
            )
        )
