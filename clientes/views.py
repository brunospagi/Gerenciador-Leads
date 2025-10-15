from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, TemplateView
from .models import Cliente, Historico
from .forms import ClienteForm, HistoricoForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Avg, Count, F, ExpressionWrapper, fields, Q
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import json


class CalendarioView(LoginRequiredMixin, TemplateView):
    template_name = 'clientes/calendario.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        base_queryset = Cliente.objects.filter(vendedor=user) if not user.is_superuser else Cliente.objects.all()
        agendamentos_qs = base_queryset.filter(status_negociacao=Cliente.StatusNegociacao.AGENDADO)
        
        eventos_calendario = []
        for agendamento in agendamentos_qs:
            eventos_calendario.append({
                'title': agendamento.nome_cliente,
                'start': agendamento.data_proximo_contato.isoformat(),
                'url': reverse('cliente_detail', args=[agendamento.pk]),
                'color': '#6f42c1',
            })
            
        context['agendamentos_json'] = json.dumps(eventos_calendario)
        return context


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clientes/cliente_list.html'
    context_object_name = 'clientes'
    paginate_by = 15

    def get_queryset(self):
        user = self.request.user
        queryset = Cliente.objects.filter(vendedor=user) if not user.is_superuser else Cliente.objects.all()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(nome_cliente__icontains=query) |
                Q(marca_veiculo__icontains=query) |
                Q(modelo_veiculo__icontains=query) |
                Q(ano_veiculo__icontains=query) |
                Q(fonte_cliente__icontains=query)
            )
        periodo = self.request.GET.get('dias')
        if periodo and periodo.isdigit():
            dias = int(periodo)
            data_limite = timezone.now() - timedelta(days=dias)
            queryset = queryset.filter(data_ultimo_contato__gte=data_limite)
        queryset = queryset.order_by('-data_ultimo_contato')
        return queryset.exclude(status_negociacao=Cliente.StatusNegociacao.FINALIZADO)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['periodo_selecionado'] = self.request.GET.get('dias', '')
        context['search_query'] = self.request.GET.get('q', '')
        user = self.request.user
        base_queryset = Cliente.objects.filter(vendedor=user) if not user.is_superuser else Cliente.objects.all()
        context['clientes_atrasados_count'] = base_queryset.filter(
            data_proximo_contato__lte=timezone.now()
        ).exclude(status_negociacao=Cliente.StatusNegociacao.FINALIZADO).count()
        return context


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = 'clientes/cliente_detail.html'
    context_object_name = 'cliente'

    def get_queryset(self):
        user = self.request.user
        return Cliente.objects.filter(vendedor=user) if not user.is_superuser else Cliente.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['historico_form'] = HistoricoForm()
        context['historicos'] = self.object.historico.all()
        return context


class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    success_url = reverse_lazy('cliente_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        cliente = form.save(commit=False)
        
        if not self.request.user.is_superuser:
            cliente.vendedor = self.request.user

        if cliente.status_negociacao != Cliente.StatusNegociacao.AGENDADO:
            cliente.data_proximo_contato = timezone.now() + timedelta(days=5)
            
        cliente.save()
        return redirect(self.success_url)


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    success_url = reverse_lazy('cliente_list')

    def get_queryset(self):
        user = self.request.user
        return Cliente.objects.filter(vendedor=user) if not user.is_superuser else Cliente.objects.all()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Pega o objeto original do banco de dados ANTES de qualquer alteração
        original_cliente = self.get_object()
        
        # Pega a instância com os novos dados do formulário, mas ainda não salva
        novo_cliente = form.save(commit=False)

        # 1. LÓGICA DE CRIAÇÃO DE HISTÓRICO
        # Compara o status antigo com o novo para ver se houve mudança
        if original_cliente.status_negociacao != novo_cliente.status_negociacao:
            # Se o novo status for "Agendado", cria o histórico detalhado
            if novo_cliente.status_negociacao == Cliente.StatusNegociacao.AGENDADO:
                data_formatada = novo_cliente.data_proximo_contato.strftime('%d/%m/%Y às %H:%M')
                motivacao = f"Visita agendada para {data_formatada} pelo vendedor {novo_cliente.vendedor.username}."
                Historico.objects.create(cliente=original_cliente, motivacao=motivacao)
            else: # Para qualquer outra mudança, cria o histórico padrão
                motivacao = f"Status alterado de '{original_cliente.get_status_negociacao_display()}' para '{novo_cliente.get_status_negociacao_display()}'."
                Historico.objects.create(cliente=original_cliente, motivacao=motivacao)

        # 2. LÓGICA PARA EVITAR ERRO 500
        # Se o campo de data não veio no formulário (o modal não foi usado),
        # restaura a data que já existia no banco de dados.
        if not form.cleaned_data.get('data_proximo_contato'):
            novo_cliente.data_proximo_contato = original_cliente.data_proximo_contato

        # 3. LÓGICA DE PERMISSÃO
        # Garante que o vendedor não seja alterado por não-superusuários
        if not self.request.user.is_superuser:
            novo_cliente.vendedor = original_cliente.vendedor
        
        # Salva o cliente com todos os dados corretos
        novo_cliente.save()
        
        return redirect(self.get_success_url())


@login_required
def adicionar_historico(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if not request.user.is_superuser and cliente.vendedor != request.user:
        raise PermissionDenied("Você não tem permissão para adicionar histórico a este cliente.")

    if request.method == 'POST':
        form = HistoricoForm(request.POST)
        if form.is_valid():
            historico = form.save(commit=False)
            historico.cliente = cliente
            historico.save()
            
            cliente.data_ultimo_contato = timezone.now()
            
            if cliente.status_negociacao != Cliente.StatusNegociacao.AGENDADO:
                cliente.data_proximo_contato = timezone.now() + timedelta(days=5)
            
            cliente.save()
            
    return redirect('cliente_detail', pk=cliente.pk)
    

# ... (Restante do arquivo como relatorios, delete, etc. permanece o mesmo)
class ClienteAtrasadoListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clientes/cliente_atrasado_list.html'
    context_object_name = 'clientes'

    def get_queryset(self):
        user = self.request.user
        queryset = Cliente.objects.filter(vendedor=user) if not user.is_superuser else Cliente.objects.all()
        queryset = queryset.filter(data_proximo_contato__lte=timezone.now())
        queryset = queryset.order_by('data_proximo_contato')
        return queryset.exclude(status_negociacao=Cliente.StatusNegociacao.FINALIZADO)

class ClienteFinalizadoListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clientes/cliente_finalizado_list.html'
    context_object_name = 'clientes'

    def get_queryset(self):
        user = self.request.user
        queryset = Cliente.objects.filter(vendedor=user) if not user.is_superuser else Cliente.objects.all()
        queryset = queryset.filter(status_negociacao=Cliente.StatusNegociacao.FINALIZADO)
        return queryset.order_by('-data_ultimo_contato')


@login_required
def relatorio_dashboard(request):
    if not request.user.profile.nivel_acesso == 'ADMIN':
        raise PermissionDenied("Você não tem permissão para acessar esta página.")

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)

    clientes_todos = Cliente.objects.filter(data_primeiro_contato__date__range=[start_date, end_date])
    total_clientes = clientes_todos.count()
    clientes_ativos = clientes_todos.exclude(status_negociacao=Cliente.StatusNegociacao.FINALIZADO)
    
    clientes_concluidos = clientes_todos.filter(status_negociacao=Cliente.StatusNegociacao.VENDIDO)

    taxa_conversao = (clientes_concluidos.count() / total_clientes) * 100 if total_clientes > 0 else 0

    tempo_medio_fechamento_delta = clientes_concluidos.annotate(
        duracao=ExpressionWrapper(F('data_ultimo_contato') - F('data_primeiro_contato'), output_field=fields.DurationField())
    ).aggregate(tempo_medio=Avg('duracao'))['tempo_medio']
    
    tempo_medio_fechamento_dias = tempo_medio_fechamento_delta.days if tempo_medio_fechamento_delta else 0

    status_data = clientes_ativos.values('status_negociacao').annotate(total=Count('id')).order_by('-total')
    status_labels = [Cliente.StatusNegociacao(item['status_negociacao']).label for item in status_data]
    status_values = [item['total'] for item in status_data]
    
    tipo_negociacao_data = clientes_todos.values('tipo_negociacao').annotate(total=Count('id')).order_by('-total')
    tipo_negociacao_labels = [Cliente.TipoNegociacao(item['tipo_negociacao']).label for item in tipo_negociacao_data]
    tipo_negociacao_values = [item['total'] for item in tipo_negociacao_data]

    vendedor_data = clientes_todos.values('vendedor__username').annotate(total=Count('id')).order_by('-total')
    vendedor_labels = [item['vendedor__username'] for item in vendedor_data]
    vendedor_values = [item['total'] for item in vendedor_data]

    vendas_data = clientes_concluidos.filter(
        tipo_negociacao=Cliente.TipoNegociacao.VENDA
    ).values('vendedor__username').annotate(total=Count('id')).order_by('-total')
    
    vendas_por_vendedor_labels = [item['vendedor__username'] for item in vendas_data]
    vendas_por_vendedor_values = [item['total'] for item in vendas_data]

    consignacao_data = clientes_concluidos.filter(
        tipo_negociacao=Cliente.TipoNegociacao.CONSIGNACAO
    ).values('vendedor__username').annotate(total=Count('id')).order_by('-total')

    consignacao_por_vendedor_labels = [item['vendedor__username'] for item in consignacao_data]
    consignacao_por_vendedor_values = [item['total'] for item in consignacao_data]

    context = {
        'total_clientes': total_clientes,
        'total_clientes_ativos': clientes_ativos.count(),
        'taxa_conversao': round(taxa_conversao, 2),
        'tempo_medio_fechamento_dias': tempo_medio_fechamento_dias,
        'status_labels': status_labels,
        'status_values': status_values,
        'tipo_negociacao_labels': tipo_negociacao_labels,
        'tipo_negociacao_values': tipo_negociacao_values,
        'vendedor_labels': vendedor_labels,
        'vendedor_values': vendedor_values,
        'start_date': start_date,
        'end_date': end_date,
        'vendas_por_vendedor_labels': vendas_por_vendedor_labels,
        'vendas_por_vendedor_values': vendas_por_vendedor_values,
        'consignacao_por_vendedor_labels': consignacao_por_vendedor_labels,
        'consignacao_por_vendedor_values': consignacao_por_vendedor_values,
    }
    
    return render(request, 'clientes/relatorios.html', context)

@login_required
def exportar_relatorio_pdf(request):
    if not request.user.profile.nivel_acesso == 'ADMIN':
        raise PermissionDenied("Você não tem permissão para acessar esta página.")

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)

    clientes_todos = Cliente.objects.filter(data_primeiro_contato__date__range=[start_date, end_date])
    total_clientes = clientes_todos.count()
    clientes_ativos = clientes_todos.exclude(status_negociacao=Cliente.StatusNegociacao.FINALIZADO)
    
    clientes_concluidos = clientes_todos.filter(status_negociacao=Cliente.StatusNegociacao.VENDIDO)

    taxa_conversao = (clientes_concluidos.count() / total_clientes) * 100 if total_clientes > 0 else 0

    tempo_medio_fechamento_delta = clientes_concluidos.annotate(
        duracao=ExpressionWrapper(F('data_ultimo_contato') - F('data_primeiro_contato'), output_field=fields.DurationField())
    ).aggregate(tempo_medio=Avg('duracao'))['tempo_medio']
    
    tempo_medio_fechamento_dias = tempo_medio_fechamento_delta.days if tempo_medio_fechamento_delta else 0

    status_data_list = clientes_ativos.values('status_negociacao').annotate(total=Count('id')).order_by('-total')
    status_data_dict = {Cliente.StatusNegociacao(item['status_negociacao']).label: item['total'] for item in status_data_list}

    tipo_negociacao_list = clientes_todos.values('tipo_negociacao').annotate(total=Count('id')).order_by('-total')
    tipo_negociacao_dict = {Cliente.TipoNegociacao(item['tipo_negociacao']).label: item['total'] for item in tipo_negociacao_list}

    vendedor_list = clientes_todos.values('vendedor__username').annotate(total=Count('id')).order_by('-total')
    vendedor_dict = {item['vendedor__username']: item['total'] for item in vendedor_list}

    vendas_list = clientes_concluidos.filter(
        tipo_negociacao=Cliente.TipoNegociacao.VENDA
    ).values('vendedor__username').annotate(total=Count('id')).order_by('-total')
    vendas_por_vendedor_dict = {item['vendedor__username']: item['total'] for item in vendas_list}

    consignacao_list = clientes_concluidos.filter(
        tipo_negociacao=Cliente.TipoNegociacao.CONSIGNACAO
    ).values('vendedor__username').annotate(total=Count('id')).order_by('-total')
    consignacao_por_vendedor_dict = {item['vendedor__username']: item['total'] for item in consignacao_list}

    context = {
        'total_clientes': total_clientes,
        'total_clientes_ativos': clientes_ativos.count(),
        'taxa_conversao': round(taxa_conversao, 2),
        'tempo_medio_fechamento_dias': tempo_medio_fechamento_dias,
        'status_data': status_data_dict,
        'tipo_negociacao_data': tipo_negociacao_dict,
        'vendedor_data': vendedor_dict,
        'start_date': start_date,
        'end_date': end_date,
        'vendas_por_vendedor_data': vendas_por_vendedor_dict,
        'consignacao_por_vendedor_data': consignacao_por_vendedor_dict,
    }
    
    template_path = 'clientes/relatorio_pdf.html'
    template = get_template(template_path)
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="relatorio_leads.pdf"'

    pisa_status = pisa.CreatePDF(
       html, dest=response)

    if pisa_status.err:
       return HttpResponse('Ocorreram alguns erros <pre>' + html + '</pre>')
    return response

class ClienteDeleteView(LoginRequiredMixin, DeleteView):
    model = Cliente
    template_name = 'clientes/cliente_confirm_delete.html'
    success_url = reverse_lazy('cliente_list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_superuser is False:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

def offline_view(request):
    return render(request, "clientes/offline.html")