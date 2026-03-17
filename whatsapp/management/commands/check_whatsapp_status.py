from django.core.management.base import BaseCommand

from whatsapp.services import reconcile_recent_outbound_statuses


class Command(BaseCommand):
    help = 'Reconcilia status de mensagens WhatsApp enviadas (pendente/enviada/entregue) para corrigir checks de entrega/leitura.'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=int, default=180, help='Janela em minutos para verificar mensagens recentes.')
        parser.add_argument('--limit', type=int, default=200, help='Quantidade maxima de mensagens para reconciliar por execucao.')
        parser.add_argument('--dry-run', action='store_true', help='Simula atualizacoes sem gravar no banco.')

    def handle(self, *args, **options):
        minutes = int(options.get('minutes') or 180)
        limit = int(options.get('limit') or 200)
        dry_run = bool(options.get('dry_run'))

        self.stdout.write(
            f'Iniciando reconciliacao de status WhatsApp (minutes={minutes}, limit={limit}, dry_run={dry_run})...'
        )

        stats = reconcile_recent_outbound_statuses(minutes=minutes, limit=limit, dry_run=dry_run)

        self.stdout.write(
            self.style.SUCCESS(
                'Concluido. '
                f"checked={stats.get('checked', 0)} "
                f"updated={stats.get('updated', 0)} "
                f"failed_lookups={stats.get('failed_lookups', 0)} "
                f"no_instance={stats.get('no_instance', 0)} "
                f"no_match={stats.get('no_match', 0)}"
            )
        )
