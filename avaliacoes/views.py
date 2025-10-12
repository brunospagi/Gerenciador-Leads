# brunospagi/gerenciador-leads/Gerenciador-Leads-fecd02772f93afa4ca06347c8334383a86eb8295/avaliacoes/views.py

from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from .models import Avaliacao, AvaliacaoFoto
from .forms import AvaliacaoForm, FotoUploadForm
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse
import requests
from django.db.models import Q

class AvaliacaoListView(LoginRequiredMixin, ListView):
    model = Avaliacao
    template_name = 'avaliacoes/avaliacao_list.html'
    context_object_name = 'avaliacoes'
    paginate_by = 10  # Define o número de itens por página

    def get_queryset(self):
        # Começa com a query base de avaliações disponíveis e recentes
        queryset = super().get_queryset().filter(
            status='disponivel',
            data_criacao__gte=timezone.now() - timedelta(days=30)
        )

        # 1. Lógica de Busca
        query = self.request.GET.get('q')
        if query:
            # Busca no modelo, marca, ano ou placa que contenham o texto da busca
            queryset = queryset.filter(
                Q(modelo__icontains=query) |
                Q(marca__icontains=query) |
                Q(ano__icontains=query) |
                Q(placa__icontains=query)
            )

        # 2. Lógica de Ordenação
        sort = self.request.GET.get('sort')
        if sort == 'antigo':
            queryset = queryset.order_by('data_criacao')
        else:
            # O padrão é ordenar pelos mais novos
            queryset = queryset.order_by('-data_criacao')

        return queryset

    def get_context_data(self, **kwargs):
        # Passa os parâmetros de busca e ordenação para o template
        # para que a paginação funcione corretamente com os filtros ativos
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['sort_order'] = self.request.GET.get('sort', 'novo')
        return context


class AvaliacaoCreateView(LoginRequiredMixin, CreateView):
    model = Avaliacao
    form_class = AvaliacaoForm
    template_name = 'avaliacoes/avaliacao_form.html'
    success_url = reverse_lazy('avaliacao_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['foto_form'] = FotoUploadForm()
        return context

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        foto_form = FotoUploadForm(request.POST, request.FILES)

        if form.is_valid() and foto_form.is_valid():
            return self.form_valid(form, foto_form)
        else:
            return self.render_to_response(
                self.get_context_data(form=form, foto_form=foto_form)
            )

    def form_valid(self, form, foto_form):
        self.object = form.save()
        files = self.request.FILES.getlist('fotos')

        try:
            for f in files[:20]:
                AvaliacaoFoto.objects.create(avaliacao=self.object, foto=f)
        except Exception as e:
            # Imprime o erro no console do servidor para depuração
            print(f"ERRO AO SALVAR ARQUIVO: {e}")
            pass

        return redirect(self.success_url)


class AvaliacaoDetailView(LoginRequiredMixin, DetailView):
    model = Avaliacao
    template_name = 'avaliacoes/avaliacao_detail.html'
    context_object_name = 'avaliacao'


class AvaliacaoUpdateView(LoginRequiredMixin, UpdateView):
    model = Avaliacao
    form_class = AvaliacaoForm
    template_name = 'avaliacoes/avaliacao_form.html'
    
    def get_success_url(self):
        return reverse_lazy('avaliacao_detail', kwargs={'pk': self.object.pk})


# --- Views da API FIPE ---

def get_fipe_marcas(request):
    """Busca as marcas de carros na API da FIPE."""
    try:
        response = requests.get('https://parallelum.com.br/fipe/api/v1/carros/marcas')
        response.raise_for_status()
        return JsonResponse(response.json(), safe=False)
    except requests.RequestException:
        return JsonResponse({'error': 'Erro ao buscar marcas'}, status=500)


def get_fipe_modelos(request, marca_id):
    """Busca os modelos de uma marca específica."""
    try:
        response = requests.get(f'https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos')
        response.raise_for_status()
        # A API retorna um dicionário com uma chave 'modelos' que contém a lista
        return JsonResponse(response.json().get('modelos', []), safe=False)
    except requests.RequestException:
        return JsonResponse({'error': 'Erro ao buscar modelos'}, status=500)


def get_fipe_anos(request, marca_id, modelo_id):
    """Busca os anos de um modelo específico."""
    try:
        response = requests.get(f'https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos')
        response.raise_for_status()
        return JsonResponse(response.json(), safe=False)
    except requests.RequestException:
        return JsonResponse({'error': 'Erro ao buscar anos'}, status=500)