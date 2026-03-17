from django.core.management.base import BaseCommand

from whatsapp.services import reconcile_presence_states


class Command(BaseCommand):
    help = 'Reconcilia estados de presenca do WhatsApp (online, digitando, gravando) para evitar status preso no frontend.'

    def add_arguments(self, parser):
        parser.add_argument('--typing-seconds', type=int, default=12, help='Expira "digitando" apos N segundos sem update.')
        parser.add_argument('--recording-seconds', type=int, default=12, help='Expira "gravando" apos N segundos sem update.')
        parser.add_argument('--online-seconds', type=int, default=45, help='Expira "online" apos N segundos sem update.')
        parser.add_argument('--limit', type=int, default=1000, help='Quantidade maxima de conversas por execucao.')
        parser.add_argument('--dry-run', action='store_true', help='Simula sem salvar no banco.')

    def handle(self, *args, **options):
        typing_seconds = int(options.get('typing_seconds') or 12)
        recording_seconds = int(options.get('recording_seconds') or 12)
        online_seconds = int(options.get('online_seconds') or 45)
        limit = int(options.get('limit') or 1000)
        dry_run = bool(options.get('dry_run'))

        self.stdout.write(
            'Iniciando reconciliacao de presenca WhatsApp '
            f'(typing={typing_seconds}s, recording={recording_seconds}s, online={online_seconds}s, limit={limit}, dry_run={dry_run})...'
        )

        stats = reconcile_presence_states(
            typing_seconds=typing_seconds,
            recording_seconds=recording_seconds,
            online_seconds=online_seconds,
            limit=limit,
            dry_run=dry_run,
        )

        self.stdout.write(
            self.style.SUCCESS(
                'Concluido. '
                f"checked={stats.get('checked', 0)} "
                f"updated={stats.get('updated', 0)} "
                f"typing_expired={stats.get('typing_expired', 0)} "
                f"recording_expired={stats.get('recording_expired', 0)} "
                f"online_expired={stats.get('online_expired', 0)} "
                f"invalid_timestamp={stats.get('invalid_timestamp', 0)} "
                f"without_presence={stats.get('without_presence', 0)}"
            )
        )
