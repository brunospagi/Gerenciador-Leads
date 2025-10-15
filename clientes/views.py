from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from .models import Cliente
from .forms import ClienteForm, HistoricoForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from datetime import timedelta
# >> 1. IMPORTE O 'Q' PARA FAZER BUSCAS COMPLEXAS <<
from django.db.models import Avg, Count, F, ExpressionWrapper, fields, Q
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from datetime import datetime


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clientes/cliente_list.html'
    context_object_name = 'clientes'
    # >> 2. DEFINA O NÚMERO DE ITENS POR PÁGINA <<
    paginate_by = 15

    def get_queryset(self):
        # Define o queryset base (todos os clientes para admin, apenas os do vendedor para os demais)
        user = self.request.user
        queryset = Cliente.objects.filter(vendedor=user) if not user.is_superuser else Cliente.objects.all()

        # >> 3. APLICA O FILTRO DE PESQUISA <<
        # Pega o valor do parâmetro 'q' da URL (?q=valor)
        query = self.request.GET.get('q')
        if query:
            # Filtra o queryset usando o 'Q' para buscar em múltiplos campos.
            # 'icontains' significa que a busca não diferencia maiúsculas de minúsculas.
            queryset = queryset.filter(
                Q(nome_cliente__icontains=query) |
                Q(modelo_veiculo__icontains=query) |
                Q(fonte_cliente__icontains=query)
            )

        # Mantém o filtro de período de último contato
        periodo = self.request.GET.get('dias')
        if periodo and periodo.isdigit():
            dias = int(periodo)
            data_limite = timezone.now() - timedelta(days=dias)
            queryset = queryset.filter(data_ultimo_contato__gte=data_limite)

        # Ordena pelo último contato e exclui os finalizados
        queryset = queryset.order_by('-data_ultimo_contato')
        return queryset.exclude(status_negociacao=Cliente.StatusNegociacao.FINALIZADO)

    def get_context_data(self, **kwargs):
        # Passa os filtros para o template para que eles possam ser mantidos
        # nos links de paginação e nos campos de formulário.
        context = super().get_context_data(**kwargs)
        context['periodo_selecionado'] = self.request.GET.get('dias', '')
        # >> 4. PASSA O VALOR DA BUSCA DE VOLTA PARA O TEMPLATE <<
        context['search_query'] = self.request.GET.get('q', '')
        
        user = self.request.user
        base_queryset = Cliente.objects.filter(vendedor=user) if not user.is_superuser else Cliente.objects.all()
        
        context['clientes_atrasados_count'] = base_queryset.filter(
            data_proximo_contato__lte=timezone.now()
        ).exclude(status_negociacao=Cliente.StatusNegociacao.FINALIZADO).count()
        
        return context

# ... (o restante do arquivo views.py continua igual) ...
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
        if not self.request.user.is_superuser:
            form.instance.vendedor = self.request.user
        return super().form_valid(form)

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
        if not self.request.user.is_superuser:
            form.instance.vendedor = self.object.vendedor
        return super().form_valid(form)

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
            cliente.data_proximo_contato = timezone.now() + timedelta(days=5)
            cliente.save()
            
    return redirect('cliente_detail', pk=cliente.pk)

@login_required
def relatorio_dashboard(request):
    if not request.user.is_superuser:
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
    clientes_finalizados = clientes_todos.filter(status_negociacao=Cliente.StatusNegociacao.FINALIZADO)

    taxa_conversao = (clientes_finalizados.count() / total_clientes) * 100 if total_clientes > 0 else 0

    tempo_medio_fechamento_delta = clientes_finalizados.annotate(
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
    }
    
    return render(request, 'clientes/relatorios.html', context)

@login_required
def exportar_relatorio_pdf(request):
    if not request.user.is_superuser:
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
    clientes_finalizados = clientes_todos.filter(status_negociacao=Cliente.StatusNegociacao.FINALIZADO)

    taxa_conversao = (clientes_finalizados.count() / total_clientes) * 100 if total_clientes > 0 else 0

    tempo_medio_fechamento_delta = clientes_finalizados.annotate(
        duracao=ExpressionWrapper(F('data_ultimo_contato') - F('data_primeiro_contato'), output_field=fields.DurationField())
    ).aggregate(tempo_medio=Avg('duracao'))['tempo_medio']
    
    tempo_medio_fechamento_dias = tempo_medio_fechamento_delta.days if tempo_medio_fechamento_delta else 0

    status_data_list = clientes_ativos.values('status_negociacao').annotate(total=Count('id')).order_by('-total')
    status_data_dict = {Cliente.StatusNegociacao(item['status_negociacao']).label: item['total'] for item in status_data_list}

    tipo_negociacao_list = clientes_todos.values('tipo_negociacao').annotate(total=Count('id')).order_by('-total')
    tipo_negociacao_dict = {Cliente.TipoNegociacao(item['tipo_negociacao']).label: item['total'] for item in tipo_negociacao_list}

    vendedor_list = clientes_todos.values('vendedor__username').annotate(total=Count('id')).order_by('-total')
    vendedor_dict = {item['vendedor__username']: item['total'] for item in vendedor_list}

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
    }
    
    template_path = 'clientes/relatorio_pdf.html' # Utiliza o novo template
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