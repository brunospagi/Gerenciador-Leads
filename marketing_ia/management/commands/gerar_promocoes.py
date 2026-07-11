from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from marketing_ia.models import VeiculoAnuncio
from marketing_ia.services import GeracaoPostError, gerar_post_para_anuncio, sincronizar_estoque

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Raspa o estoque público de spagimotors.com.br/search, salva/atualiza os '
        'anúncios e gera posts promocionais (foto + legenda) com IA para os '
        'veículos que ainda não têm um post.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--max-paginas', type=int, default=None,
                             help='Limita quantas páginas de /search percorrer.')
        parser.add_argument('--tipo', choices=['CARRO', 'MOTO'], default=None,
                             help='Filtra por tipo de veículo.')
        parser.add_argument('--limit', type=int, default=None,
                             help='Limita quantos anúncios coletar em detalhe no scraping.')
        parser.add_argument('--somente-scraping', action='store_true',
                             help='Só coleta/atualiza os anúncios, sem gerar posts com IA.')
        parser.add_argument('--forcar-regeneracao', action='store_true',
                             help='Gera um novo post mesmo para anúncios que já têm um.')
        parser.add_argument('--limit-posts', type=int, default=None,
                             help='Limita quantos posts novos gerar com IA nesta execução (controla custo de API).')
        parser.add_argument('--usuario', type=str, default=None,
                             help='Username a associar como gerado_por nos posts criados.')

    def handle(self, *args, **options):
        self.stdout.write('Raspando estoque de spagimotors.com.br/search...')
        resultado = sincronizar_estoque(
            max_paginas=options['max_paginas'],
            tipo=options['tipo'],
            limit=options['limit'],
        )
        self.stdout.write(self.style.SUCCESS(
            f"{resultado['total']} anúncios coletados "
            f"({resultado['criados']} novo(s), {resultado['atualizados']} atualizado(s), "
            f"{resultado['desativados']} saiu(íram) do estoque)."
        ))

        if options['somente_scraping']:
            return

        if not resultado['total']:
            self.stdout.write(self.style.WARNING('Nenhum anúncio coletado, nada para gerar.'))
            return

        usuario = None
        if options['usuario']:
            usuario = User.objects.filter(username=options['usuario']).first()

        qs = VeiculoAnuncio.objects.filter(ativo=True)
        if not options['forcar_regeneracao']:
            qs = qs.filter(posts__isnull=True)
        else:
            qs = qs.distinct()

        limit_posts = options['limit_posts']
        if limit_posts:
            qs = qs[:limit_posts]

        self.stdout.write(f'Gerando posts promocionais para {qs.count()} anúncio(s)...')

        gerados, falhas = 0, 0
        for anuncio in qs:
            try:
                gerar_post_para_anuncio(anuncio, usuario=usuario)
            except GeracaoPostError as exc:
                self.stdout.write(self.style.WARNING(f'[pula] {anuncio.titulo}: {exc}'))
                falhas += 1
                continue
            gerados += 1
            self.stdout.write(self.style.SUCCESS(f'[ok] {anuncio.titulo}'))

        self.stdout.write(self.style.SUCCESS(f'Concluído: {gerados} post(s) gerado(s), {falhas} falha(s).'))
