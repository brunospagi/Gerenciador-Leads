from django.core.management.base import BaseCommand
from vendas_produtos.models import VendaProduto


class Command(BaseCommand):
    help = 'Recalcula split de comissao para vendas com ajudante (50/50 ou configuracao atual).'

    def add_arguments(self, parser):
        parser.add_argument('--mes', type=int, help='Mes de referencia (1-12).')
        parser.add_argument('--ano', type=int, help='Ano de referencia (YYYY).')
        parser.add_argument('--dry-run', action='store_true', help='Apenas simula sem salvar.')

    def handle(self, *args, **options):
        mes = options.get('mes')
        ano = options.get('ano')
        dry_run = bool(options.get('dry_run'))

        qs = VendaProduto.objects.filter(
            status='APROVADO',
            vendedor_ajudante__isnull=False,
            tipo_produto__in=['VENDA_VEICULO', 'VENDA_MOTO', 'REFINANCIAMENTO'],
        ).select_related('vendedor', 'vendedor_ajudante')

        if mes:
            qs = qs.filter(data_venda__month=mes)
        if ano:
            qs = qs.filter(data_venda__year=ano)

        total = qs.count()
        changed = 0
        processed = 0

        self.stdout.write(
            f'Iniciando recálculo de split de ajuda. total={total} mes={mes or "*"} ano={ano or "*"} dry_run={dry_run}'
        )

        for venda in qs.iterator():
            processed += 1
            before = (
                venda.comissao_vendedor,
                venda.comissao_ajudante,
                venda.lucro_loja,
            )
            if dry_run:
                continue

            venda.save()
            after = (
                venda.comissao_vendedor,
                venda.comissao_ajudante,
                venda.lucro_loja,
            )

            if before != after:
                changed += 1
                self.stdout.write(f'- venda_id={venda.id} {before} -> {after}')

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'Concluído (dry-run). candidatas={processed}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Concluído. alteradas={changed} de {total}'))
