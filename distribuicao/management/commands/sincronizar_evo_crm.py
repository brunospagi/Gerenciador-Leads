from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from clientes.models import Cliente
from distribuicao.logic import criar_lead_evo_crm


class Command(BaseCommand):
    help = (
        'Reprocessa clientes recentes que ainda nao foram sincronizados com o Evo CRM '
        '(evo_crm_lead_id/evo_crm_deal_id vazios), reconciliando falhas transitorias da API.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=7,
            help='Janela em dias de leads recentes a considerar para retry (padrao: 7).',
        )

    def handle(self, *args, **options):
        dias = options['dias']
        desde = timezone.now() - timedelta(days=dias)

        pendentes = Cliente.objects.filter(
            data_primeiro_contato__gte=desde,
        ).filter(
            Q(evo_crm_lead_id__isnull=True) | Q(evo_crm_lead_id=''),
        )

        total = pendentes.count()
        if not total:
            self.stdout.write(self.style.SUCCESS('Nenhum lead pendente de sincronizacao com o Evo CRM.'))
            return

        self.stdout.write(f'Reprocessando {total} lead(s) sem sincronizacao confirmada com o Evo CRM...')

        sucesso = 0
        falha = 0
        for cliente in pendentes:
            resultado = criar_lead_evo_crm(cliente)
            if resultado.get('success'):
                sucesso += 1
            else:
                falha += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Cliente {cliente.pk} ({cliente.nome_cliente}): falha ao sincronizar - "
                        f"{resultado.get('error') or resultado.get('reason')}"
                    )
                )

        self.stdout.write(self.style.SUCCESS(f'Concluido: {sucesso} sincronizado(s), {falha} com falha.'))
