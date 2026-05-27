from django.utils import timezone

from .models import TVProgramacaoItem


def _match_data(item, data_atual):
    if item.data_inicio and data_atual < item.data_inicio:
        return False
    if item.data_fim and data_atual > item.data_fim:
        return False
    return True


def _match_dia_semana(item, weekday):
    dias = {d.strip() for d in (item.dias_semana or '').split(',') if d.strip()}
    return str(weekday) in dias


def _match_horario(item, hora_atual):
    inicio = item.horario_inicio
    fim = item.horario_fim

    if not inicio and not fim:
        return True
    if inicio and not fim:
        return hora_atual >= inicio
    if fim and not inicio:
        return hora_atual <= fim

    if inicio <= fim:
        return inicio <= hora_atual <= fim

    # Janela que cruza meia-noite, ex.: 22:00 até 02:00
    return hora_atual >= inicio or hora_atual <= fim


def _is_item_ativo(item, data_atual, hora_atual, weekday):
    if not _match_data(item, data_atual):
        return False
    if not _match_dia_semana(item, weekday):
        return False
    if not _match_horario(item, hora_atual):
        return False
    return True


def get_tv_programacao_ativa_lista(agora=None):
    agora = timezone.localtime(agora or timezone.now())
    data_atual = agora.date()
    hora_atual = agora.time()
    weekday = agora.weekday()

    candidatos = TVProgramacaoItem.objects.filter(ativo=True).order_by('ordem', 'id')
    return [
        item for item in candidatos
        if _is_item_ativo(item, data_atual, hora_atual, weekday)
    ]


def get_tv_programacao_ativa(agora=None):
    ativos = get_tv_programacao_ativa_lista(agora=agora)
    return ativos[0] if ativos else None
