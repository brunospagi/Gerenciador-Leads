import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import RegistroPonto, ConfiguracaoPonto
from funcionarios.models import Funcionario
from .forms import RegistroPontoForm

def obter_ip_cliente(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

@login_required
def relogio_ponto(request):
    funcionario = getattr(request.user, 'dados_funcionais', None)
    
    if not funcionario:
        messages.error(request, "Acesso Negado: O seu utilizador não possui ficha no RH.")
        return redirect('/')

    config = ConfiguracaoPonto.load()
    ip_atual = obter_ip_cliente(request)
    
    if config.ip_permitido != '*' and ip_atual != config.ip_permitido:
        messages.error(request, f"Acesso Negado 🚫 O ponto só pode ser registrado na rede Wi-Fi da Loja! (Seu IP atual: {ip_atual})")
        return redirect('/')

    hoje = timezone.now().date()
    agora = timezone.now().time()
    
    ponto, created = RegistroPonto.objects.get_or_create(funcionario=funcionario, data=hoje)

    if request.method == 'POST':
        tipo_batida = request.POST.get('tipo_batida')
        foto_base64 = request.POST.get('foto_base64')
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        
        if not foto_base64:
            messages.error(request, "Falha ao receber a foto. Tente novamente.")
            return redirect('controle_ponto:relogio')

        if tipo_batida == 'entrada' and not ponto.entrada:
            ponto.entrada = agora
            ponto.foto_entrada = foto_base64
            messages.success(request, f"Entrada registrada com sucesso às {agora.strftime('%H:%M')}")
        elif tipo_batida == 'saida_almoco' and not ponto.saida_almoco:
            ponto.saida_almoco = agora
            ponto.foto_saida_almoco = foto_base64
            messages.success(request, f"Saída para almoço às {agora.strftime('%H:%M')}")
        elif tipo_batida == 'retorno_almoco' and not ponto.retorno_almoco:
            ponto.retorno_almoco = agora
            ponto.foto_retorno_almoco = foto_base64
            messages.success(request, f"Retorno do almoço às {agora.strftime('%H:%M')}")
        elif tipo_batida == 'saida' and not ponto.saida:
            ponto.saida = agora
            ponto.foto_saida = foto_base64
            messages.success(request, f"Fim de expediente às {agora.strftime('%H:%M')}. Bom descanso!")
        else:
            messages.warning(request, "Batida inválida ou já registrada.")
            return redirect('controle_ponto:relogio')

        ponto.ip_registrado = ip_atual
        if lat and lng:
            ponto.latitude = lat
            ponto.longitude = lng
        
        ponto.save()
        return redirect('controle_ponto:relogio')

    foto_url = funcionario.foto_biometria.url if funcionario.foto_biometria else None

    return render(request, 'controle_ponto/relogio.html', {
        'ponto': ponto,
        'ip_atual': ip_atual,
        'foto_url': foto_url,
        'config': config,
    })

@login_required
def mapa_pontos(request):
    nivel = getattr(request.user.profile, 'nivel_acesso', '')
    if not request.user.is_superuser and nivel not in ['ADMIN', 'GERENTE']:
        messages.error(request, "Acesso negado ao mapa de auditoria.")
        return redirect('/')

    data_str = request.GET.get('data')
    if data_str:
        data_filtro = datetime.strptime(data_str, '%Y-%m-%d').date()
    else:
        data_filtro = timezone.now().date()

    pontos = RegistroPonto.objects.filter(data=data_filtro).exclude(latitude__isnull=True).exclude(latitude__exact='')

    pontos_json = []
    for p in pontos:
        try:
            foto_perfil = p.funcionario.foto_biometria.url if p.funcionario.foto_biometria else None
            pontos_json.append({
                'nome': p.funcionario.nome_completo,
                'cargo': p.funcionario.cargo,
                'lat': float(p.latitude),
                'lng': float(p.longitude),
                'entrada': p.entrada.strftime('%H:%M') if p.entrada else '--:--',
                'saida': p.saida.strftime('%H:%M') if p.saida else '--:--',
                'ip': p.ip_registrado,
                'foto': foto_perfil
            })
        except ValueError:
            pass

    context = {
        'data_filtro': data_filtro.strftime('%Y-%m-%d'),
        'pontos_json': json.dumps(pontos_json),
    }
    return render(request, 'controle_ponto/mapa.html', context)

@login_required
def relatorio_mensal(request):
    nivel = getattr(request.user.profile, 'nivel_acesso', '')
    if not request.user.is_superuser and nivel not in ['ADMIN', 'GERENTE']:
        messages.error(request, "Acesso negado ao espelho de ponto.")
        return redirect('/')

    hoje = timezone.now().date()
    mes = int(request.GET.get('mes', hoje.month))
    ano = int(request.GET.get('ano', hoje.year))
    funcionario_id = request.GET.get('funcionario')

    pontos = RegistroPonto.objects.filter(data__month=mes, data__year=ano).select_related('funcionario').order_by('data', 'funcionario__user__first_name')

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

# ==========================================
# VIEWS DE ADMINISTRAÇÃO (EDTAR E EXCLUIR)
# ==========================================

class RegistroPontoUpdateView(LoginRequiredMixin, UpdateView):
    model = RegistroPonto
    form_class = RegistroPontoForm
    template_name = 'controle_ponto/form_ponto.html'
    success_url = reverse_lazy('controle_ponto:relatorio_mensal')

    def dispatch(self, request, *args, **kwargs):
        nivel = getattr(request.user.profile, 'nivel_acesso', '')
        if not request.user.is_superuser and nivel not in ['ADMIN', 'GERENTE']:
            messages.error(request, "Acesso Negado: Apenas gestores podem alterar pontos manuais.")
            return redirect('/')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Registro de ponto atualizado com sucesso! (Correção Manual)")
        return super().form_valid(form)

class RegistroPontoDeleteView(LoginRequiredMixin, DeleteView):
    model = RegistroPonto
    template_name = 'controle_ponto/delete_ponto.html'
    success_url = reverse_lazy('controle_ponto:relatorio_mensal')

    def dispatch(self, request, *args, **kwargs):
        nivel = getattr(request.user.profile, 'nivel_acesso', '')
        if not request.user.is_superuser and nivel not in ['ADMIN', 'GERENTE']:
            messages.error(request, "Acesso Negado: Sem permissão para excluir pontos.")
            return redirect('/')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.warning(self.request, "Registro de ponto excluído permanentemente.")
        return super().form_valid(form)
@login_required
def detalhe_ponto(request, pk):
    # Proteção: Apenas gestores podem ver a auditoria detalhada
    nivel = getattr(request.user.profile, 'nivel_acesso', '')
    if not request.user.is_superuser and nivel not in ['ADMIN', 'GERENTE']:
        messages.error(request, "Acesso Negado: Sem permissão para ver auditoria de ponto.")
        return redirect('/')

    # Busca o ponto exato pelo ID
    ponto = get_object_or_404(RegistroPonto, pk=pk)

    return render(request, 'controle_ponto/detalhe_ponto.html', {
        'ponto': ponto
    })