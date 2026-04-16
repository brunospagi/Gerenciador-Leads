import json
import threading
from datetime import datetime
import secrets

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView, UpdateView

from funcionarios.models import Funcionario

from .forms import RegistroPontoForm
from .models import ConfiguracaoPonto, RegistroPonto

TOKEN_PONTO_TTL_SECONDS = 120
GEO_CHECK_TTL_SECONDS = 120


def obter_ip_cliente(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def _is_gestor(user):
    nivel = getattr(getattr(user, 'profile', None), 'nivel_acesso', '')
    return bool(user.is_superuser or nivel in ['ADMIN', 'GERENTE'])


def _calcular_atraso_minutos(data_ref, horario_real, horario_escala):
    if not horario_real or not horario_escala:
        return 0
    dt_real = datetime.combine(data_ref, horario_real)
    dt_escala = datetime.combine(data_ref, horario_escala)
    delta = dt_real - dt_escala
    atraso = int(delta.total_seconds() // 60)
    return atraso if atraso > 0 else 0


@login_required
def relogio_ponto(request):
    funcionario = getattr(request.user, 'dados_funcionais', None)

    if not funcionario:
        messages.error(request, 'Acesso negado: o seu usuário não possui ficha no RH.')
        return redirect('/')

    config = ConfiguracaoPonto.load()
    ip_atual = obter_ip_cliente(request)

    if config.ip_permitido != '*' and ip_atual != config.ip_permitido:
        messages.error(request, f"Acesso negado. O ponto só pode ser registrado na rede da loja. (IP atual: {ip_atual})")
        return redirect('/')

    momento_atual = timezone.localtime()
    hoje = momento_atual.date()
    agora = momento_atual.time().replace(second=0, microsecond=0)

    ponto, _ = RegistroPonto.objects.get_or_create(funcionario=funcionario, data=hoje)

    if request.method == 'POST':
        token_form = (request.POST.get('ponto_token') or '').strip()
        token_sessao = (request.session.get('ponto_token') or '').strip()
        token_gerado_em = request.session.get('ponto_token_issued_at')
        agora_epoch = int(timezone.now().timestamp())

        token_expirado = False
        if not token_gerado_em:
            token_expirado = True
        else:
            try:
                token_expirado = (agora_epoch - int(token_gerado_em)) > TOKEN_PONTO_TTL_SECONDS
            except Exception:
                token_expirado = True

        if not token_form or token_form != token_sessao or token_expirado:
            messages.error(
                request,
                'Sessão de registro expirada (mais de 2 minutos) ou inválida. '
                'Atualize a página e tente novamente.',
            )
            return redirect('controle_ponto:relogio')

        tipo_batida = request.POST.get('tipo_batida')
        foto_base64 = request.POST.get('foto_base64')
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        geo_checked_at = request.POST.get('geo_checked_at')
        justificativa_atraso = (request.POST.get('justificativa_atraso') or '').strip()

        if not lat or not lng:
            messages.error(request, 'Localização não validada. Aguarde o GPS e tente novamente.')
            return redirect('controle_ponto:relogio')

        if not geo_checked_at:
            messages.error(request, 'Validação de localização expirou. Atualize a página e tente novamente.')
            return redirect('controle_ponto:relogio')

        try:
            geo_checked_at = int(float(geo_checked_at))
            geo_expirada = (agora_epoch - geo_checked_at) > GEO_CHECK_TTL_SECONDS
        except Exception:
            geo_expirada = True
        if geo_expirada:
            messages.error(
                request,
                'Localização expirada (mais de 2 minutos). Atualize a localização na página e tente novamente.',
            )
            return redirect('controle_ponto:relogio')

        if not foto_base64:
            messages.error(request, 'Falha ao receber a foto. Tente novamente.')
            return redirect('controle_ponto:relogio')

        evento_registrado = None

        if tipo_batida == 'entrada' and not ponto.entrada:
            atraso_minutos = _calcular_atraso_minutos(hoje, agora, config.horario_escala_entrada)
            exige_justificativa = atraso_minutos >= int(config.tolerancia_atraso_minutos or 5)

            if exige_justificativa and not justificativa_atraso:
                messages.error(
                    request,
                    f'Atraso de {atraso_minutos} min detectado. Informe a justificativa para registrar a entrada.',
                )
                return redirect('controle_ponto:relogio')

            ponto.entrada = agora
            ponto.foto_entrada = foto_base64
            ponto.horario_escala_entrada = config.horario_escala_entrada
            ponto.tolerancia_entrada_minutos = int(config.tolerancia_atraso_minutos or 5)
            ponto.atraso_minutos = atraso_minutos
            ponto.justificativa_atraso = justificativa_atraso if atraso_minutos > 0 else ''

            if atraso_minutos >= ponto.tolerancia_entrada_minutos:
                ponto.status_homologacao = RegistroPonto.StatusHomologacao.PENDENTE
                ponto.homologado_por = None
                ponto.homologado_em = None
                ponto.observacao_homologacao = ''
                messages.warning(request, f'Entrada registrada às {agora.strftime("%H:%M")}. Ocorrência enviada para homologação.')
            else:
                ponto.status_homologacao = RegistroPonto.StatusHomologacao.NAO_APLICA
                ponto.homologado_por = None
                ponto.homologado_em = None
                ponto.observacao_homologacao = ''
                messages.success(request, f'Entrada registrada com sucesso às {agora.strftime("%H:%M")}.')

            evento_registrado = 'Entrada'

        elif tipo_batida == 'saida_almoco' and not ponto.saida_almoco:
            ponto.saida_almoco = agora
            ponto.foto_saida_almoco = foto_base64
            evento_registrado = 'Saída Almoço'
            messages.success(request, f'Saída para almoço às {agora.strftime("%H:%M")}.')

        elif tipo_batida == 'retorno_almoco' and not ponto.retorno_almoco:
            ponto.retorno_almoco = agora
            ponto.foto_retorno_almoco = foto_base64
            evento_registrado = 'Retorno Almoço'
            messages.success(request, f'Retorno do almoço às {agora.strftime("%H:%M")}.')

        elif tipo_batida == 'saida' and not ponto.saida:
            ponto.saida = agora
            ponto.foto_saida = foto_base64
            evento_registrado = 'Saída Final'
            messages.success(request, f'Fim de expediente às {agora.strftime("%H:%M")}. Bom descanso!')
        else:
            messages.warning(request, 'Batida inválida ou já registrada.')
            return redirect('controle_ponto:relogio')

        ponto.ip_registrado = ip_atual
        if lat and lng:
            ponto.latitude = lat
            ponto.longitude = lng

        ponto.save()

        def disparar_webhook(dados_webhook):
            try:
                url_webhook = getattr(settings, 'WEBHOOK_PONTO_URL', None)
                if not url_webhook:
                    return
                requests.post(url_webhook, json=dados_webhook, timeout=5)
            except Exception:
                return

        payload = {
            'evento': 'novo_ponto',
            'funcionario_id': funcionario.id,
            'funcionario_nome': getattr(funcionario, 'nome_completo', str(funcionario)),
            'tipo_batida': evento_registrado,
            'data': hoje.strftime('%Y-%m-%d'),
            'hora': agora.strftime('%H:%M:%S'),
            'ip_registrado': ip_atual,
            'latitude': lat,
            'longitude': lng,
            'atraso_minutos': ponto.atraso_minutos,
            'status_homologacao': ponto.status_homologacao,
        }
        threading.Thread(target=disparar_webhook, args=(payload,), daemon=True).start()

        return redirect('controle_ponto:relogio')

    foto_url = funcionario.foto_biometria.url if funcionario.foto_biometria else None
    ponto_token = secrets.token_urlsafe(24)
    request.session['ponto_token'] = ponto_token
    request.session['ponto_token_issued_at'] = int(timezone.now().timestamp())
    return render(
        request,
        'controle_ponto/relogio.html',
        {
            'ponto': ponto,
            'ip_atual': ip_atual,
            'foto_url': foto_url,
            'config': config,
            'ponto_token': ponto_token,
            'ponto_token_ttl_seconds': TOKEN_PONTO_TTL_SECONDS,
            'ponto_token_issued_at': request.session.get('ponto_token_issued_at'),
        },
    )


@login_required
def mapa_pontos(request):
    if not _is_gestor(request.user):
        messages.error(request, 'Acesso negado ao mapa de auditoria.')
        return redirect('/')

    data_str = request.GET.get('data')
    if data_str:
        try:
            data_filtro = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            data_filtro = timezone.now().date()
    else:
        data_filtro = timezone.now().date()

    pontos = RegistroPonto.objects.filter(data=data_filtro).exclude(latitude__isnull=True).exclude(latitude__exact='')

    pontos_json = []
    for p in pontos:
        try:
            foto_perfil = p.funcionario.foto_biometria.url if p.funcionario.foto_biometria else None
            pontos_json.append(
                {
                    'nome': p.funcionario.nome_completo,
                    'cargo': p.funcionario.cargo,
                    'lat': float(p.latitude),
                    'lng': float(p.longitude),
                    'entrada': p.entrada.strftime('%H:%M') if p.entrada else '--:--',
                    'saida': p.saida.strftime('%H:%M') if p.saida else '--:--',
                    'ip': p.ip_registrado,
                    'foto': foto_perfil,
                }
            )
        except ValueError:
            pass

    context = {'data_filtro': data_filtro.strftime('%Y-%m-%d'), 'pontos_json': json.dumps(pontos_json)}
    return render(request, 'controle_ponto/mapa.html', context)


@login_required
def relatorio_mensal(request):
    if not _is_gestor(request.user):
        messages.error(request, 'Acesso negado ao espelho de ponto.')
        return redirect('/')

    hoje = timezone.now().date()
    mes = int(request.GET.get('mes', hoje.month))
    ano = int(request.GET.get('ano', hoje.year))
    funcionario_id = request.GET.get('funcionario')

    pontos = (
        RegistroPonto.objects.filter(data__month=mes, data__year=ano)
        .select_related('funcionario', 'homologado_por')
        .order_by('data', 'funcionario__user__first_name')
    )
    if funcionario_id:
        pontos = pontos.filter(funcionario_id=funcionario_id)

    funcionarios_list = Funcionario.objects.filter(ativo=True).order_by('user__first_name')
    context = {
        'pontos': pontos,
        'mes_atual': mes,
        'ano_atual': ano,
        'funcionario_selecionado': int(funcionario_id) if funcionario_id else '',
        'funcionarios': funcionarios_list,
        'meses': range(1, 13),
        'anos': range(hoje.year - 2, hoje.year + 2),
    }
    return render(request, 'controle_ponto/relatorio.html', context)


@login_required
def ocorrencias_mensais(request):
    if not _is_gestor(request.user):
        messages.error(request, 'Acesso negado às ocorrências de ponto.')
        return redirect('/')

    hoje = timezone.now().date()
    mes = int(request.GET.get('mes', hoje.month))
    ano = int(request.GET.get('ano', hoje.year))
    funcionario_id = request.GET.get('funcionario')
    status = request.GET.get('status', RegistroPonto.StatusHomologacao.PENDENTE)

    ocorrencias = (
        RegistroPonto.objects.filter(data__month=mes, data__year=ano, atraso_minutos__gt=0)
        .select_related('funcionario', 'homologado_por')
        .order_by('-data', 'funcionario__user__first_name')
    )
    if funcionario_id:
        ocorrencias = ocorrencias.filter(funcionario_id=funcionario_id)
    if status:
        ocorrencias = ocorrencias.filter(status_homologacao=status)

    funcionarios_list = Funcionario.objects.filter(ativo=True).order_by('user__first_name')
    context = {
        'ocorrencias': ocorrencias,
        'mes_atual': mes,
        'ano_atual': ano,
        'funcionario_selecionado': int(funcionario_id) if funcionario_id else '',
        'status_selecionado': status,
        'funcionarios': funcionarios_list,
        'status_choices': RegistroPonto.StatusHomologacao.choices,
        'meses': range(1, 13),
        'anos': range(hoje.year - 2, hoje.year + 2),
    }
    return render(request, 'controle_ponto/ocorrencias_mensais.html', context)


@login_required
@require_POST
def homologar_ocorrencia(request, pk):
    if not _is_gestor(request.user):
        messages.error(request, 'Acesso negado para homologar ocorrência.')
        return redirect('/')

    ponto = get_object_or_404(RegistroPonto, pk=pk)
    acao = (request.POST.get('acao') or '').strip().lower()
    observacao = (request.POST.get('observacao') or '').strip()

    if acao == 'aceitar':
        ponto.status_homologacao = RegistroPonto.StatusHomologacao.ACEITO
        messages.success(request, 'Ocorrência homologada como ACEITA.')
    elif acao == 'recusar':
        ponto.status_homologacao = RegistroPonto.StatusHomologacao.RECUSADO
        messages.warning(request, 'Ocorrência homologada como RECUSADA.')
    else:
        messages.error(request, 'Ação inválida de homologação.')
        return redirect('controle_ponto:ocorrencias_mensais')

    ponto.homologado_por = request.user
    ponto.homologado_em = timezone.now()
    ponto.observacao_homologacao = observacao
    ponto.save(update_fields=['status_homologacao', 'homologado_por', 'homologado_em', 'observacao_homologacao'])

    mes = request.POST.get('mes')
    ano = request.POST.get('ano')
    funcionario = request.POST.get('funcionario')
    status = request.POST.get('status')
    base_url = reverse_lazy('controle_ponto:ocorrencias_mensais')
    params = []
    if mes:
        params.append(f'mes={mes}')
    if ano:
        params.append(f'ano={ano}')
    if funcionario:
        params.append(f'funcionario={funcionario}')
    if status:
        params.append(f'status={status}')
    if params:
        return redirect(f'{base_url}?{"&".join(params)}')
    return redirect(base_url)


@login_required
def relatorio_entradas(request):
    if not _is_gestor(request.user):
        messages.error(request, 'Acesso negado ao relatório de entradas.')
        return redirect('/')

    hoje = timezone.now().date()
    mes = int(request.GET.get('mes', hoje.month))
    ano = int(request.GET.get('ano', hoje.year))
    funcionario_id = request.GET.get('funcionario')

    entradas = (
        RegistroPonto.objects.filter(data__month=mes, data__year=ano, entrada__isnull=False)
        .select_related('funcionario')
        .order_by('funcionario__user__first_name', 'data')
    )
    if funcionario_id:
        entradas = entradas.filter(funcionario_id=funcionario_id)

    resumo = (
        entradas.values('funcionario_id', 'funcionario__user__first_name', 'funcionario__user__last_name')
        .annotate(total_dias=Count('id'), total_atrasos=Count('id', filter=Q(atraso_minutos__gt=0)), media_atraso=Avg('atraso_minutos'))
        .order_by('funcionario__user__first_name', 'funcionario__user__last_name')
    )

    funcionarios_list = Funcionario.objects.filter(ativo=True).order_by('user__first_name')
    context = {
        'entradas': entradas,
        'resumo': resumo,
        'mes_atual': mes,
        'ano_atual': ano,
        'funcionario_selecionado': int(funcionario_id) if funcionario_id else '',
        'funcionarios': funcionarios_list,
        'meses': range(1, 13),
        'anos': range(hoje.year - 2, hoje.year + 2),
    }
    return render(request, 'controle_ponto/relatorio_entradas.html', context)


class RegistroPontoUpdateView(LoginRequiredMixin, UpdateView):
    model = RegistroPonto
    form_class = RegistroPontoForm
    template_name = 'controle_ponto/form_ponto.html'
    success_url = reverse_lazy('controle_ponto:relatorio_mensal')

    def dispatch(self, request, *args, **kwargs):
        if not _is_gestor(request.user):
            messages.error(request, 'Acesso negado: apenas gestores podem alterar pontos manuais.')
            return redirect('/')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        ponto = form.instance
        if ponto.status_homologacao in [RegistroPonto.StatusHomologacao.ACEITO, RegistroPonto.StatusHomologacao.RECUSADO]:
            ponto.homologado_por = self.request.user
            ponto.homologado_em = timezone.now()
        elif ponto.status_homologacao in [RegistroPonto.StatusHomologacao.NAO_APLICA, RegistroPonto.StatusHomologacao.PENDENTE]:
            ponto.homologado_por = None
            ponto.homologado_em = None
            if ponto.status_homologacao == RegistroPonto.StatusHomologacao.NAO_APLICA:
                ponto.observacao_homologacao = ''

        messages.success(self.request, 'Registro de ponto atualizado com sucesso!')
        return super().form_valid(form)


class RegistroPontoDeleteView(LoginRequiredMixin, DeleteView):
    model = RegistroPonto
    template_name = 'controle_ponto/delete_ponto.html'
    success_url = reverse_lazy('controle_ponto:relatorio_mensal')

    def dispatch(self, request, *args, **kwargs):
        if not _is_gestor(request.user):
            messages.error(request, 'Acesso negado: sem permissão para excluir pontos.')
            return redirect('/')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.warning(self.request, 'Registro de ponto excluído permanentemente.')
        return super().form_valid(form)


@login_required
def detalhe_ponto(request, pk):
    if not _is_gestor(request.user):
        messages.error(request, 'Acesso negado: sem permissão para ver auditoria de ponto.')
        return redirect('/')

    ponto = get_object_or_404(RegistroPonto, pk=pk)
    return render(request, 'controle_ponto/detalhe_ponto.html', {'ponto': ponto})

