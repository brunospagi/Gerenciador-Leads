from django.test import TestCase
from django.utils import timezone
from datetime import datetime

from .models import TVProgramacaoItem
from .services import get_tv_programacao_ativa, get_tv_programacao_ativa_lista


class TVProgramacaoServiceTests(TestCase):
    def test_retorna_item_ativo_por_ordem(self):
        TVProgramacaoItem.objects.create(
            titulo="Item 2",
            video_url="https://example.com/2.mp4",
            ordem=2,
            dias_semana='0,1,2,3,4,5,6',
        )
        esperado = TVProgramacaoItem.objects.create(
            titulo="Item 1",
            video_url="https://example.com/1.mp4",
            ordem=1,
            dias_semana='0,1,2,3,4,5,6',
        )

        agora = timezone.make_aware(datetime(2026, 5, 27, 10, 0, 0))
        atual = get_tv_programacao_ativa(agora)

        self.assertEqual(atual.id, esperado.id)

    def test_lista_ativa_respeita_ordem(self):
        primeiro = TVProgramacaoItem.objects.create(
            titulo="Primeiro",
            video_url="https://example.com/primeiro.mp4",
            ordem=1,
            dias_semana='0,1,2,3,4,5,6',
        )
        segundo = TVProgramacaoItem.objects.create(
            titulo="Segundo",
            video_url="https://example.com/segundo.mp4",
            ordem=2,
            dias_semana='0,1,2,3,4,5,6',
        )

        agora = timezone.make_aware(datetime(2026, 5, 27, 10, 0, 0))
        ativos = get_tv_programacao_ativa_lista(agora)

        self.assertEqual([item.id for item in ativos], [primeiro.id, segundo.id])

    def test_respeita_janela_horario_cruzando_meia_noite(self):
        item = TVProgramacaoItem.objects.create(
            titulo="Madrugada",
            video_url="https://example.com/madrugada.mp4",
            horario_inicio=datetime.strptime("22:00", "%H:%M").time(),
            horario_fim=datetime.strptime("02:00", "%H:%M").time(),
            dias_semana='0,1,2,3,4,5,6',
            ordem=0,
        )

        agora = timezone.make_aware(datetime(2026, 5, 27, 23, 30, 0))
        atual = get_tv_programacao_ativa(agora)

        self.assertEqual(atual.id, item.id)
