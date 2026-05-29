from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.backup_utils import create_system_backup


class Command(BaseCommand):
    help = "Gera backup completo do sistema em arquivo .zip"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            dest="output_dir",
            default=None,
            help="Diretorio de saida do backup (padrao: ./backups)",
        )

    def handle(self, *args, **options):
        output_dir = options.get("output_dir")
        try:
            backup_path = create_system_backup(output_dir=output_dir)
        except Exception as exc:  # pragma: no cover - erro operacional
            raise CommandError(f"Falha ao gerar backup: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Backup gerado com sucesso: {Path(backup_path)}"))
