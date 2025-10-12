# brunospagi/gerenciador-leads/Gerenciador-Leads-fecd02772f93afa4ca06347c8334383a86eb8295/avaliacoes/views.py

from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView # 1. Adicione DeleteView
from .models import Avaliacao, AvaliacoFoto
from .forms import AvaliacaoForm, FotoUploadForm
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse
import requests
from django.db.models import Q
from django.core.exceptions import PermissionDenied # 2. Importe PermissionDenied

# ... (Suas outras views como AvaliacaoListView, AvaliacaoCreateView, etc., continuam aqui) ...
class AvaliacaoListView(LoginRequiredMixin, ListView):
    model = Avaliacao
    template_name = 'avaliacoes/avaliacao_list.html'
    context_object_name = 'avaliacoes'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            status='disponivel',
            data_criacao__gte=timezone.now() - timedelta(days=30)
        )
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(modelo__icontains=query) |
                Q(marca__icontains=query) |
                Q(ano__icontains=query) |
                Q(placa__icontains=query)
            )
        sort = self.request.GET.get('sort')
        if sort == 'antigo':
            queryset = queryset.order_by('data_criacao')
        else:
            queryset = queryset.order_by('-data_criacao')
        return queryset

    def get_context_data(self, **kwargs):
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
        avaliacao = form.save(commit=False)
        avaliacao.cadastrado_por = self.request.user
        avaliacao.save()
        
        self.object = avaliacao

        files = self.request.FILES.getlist('fotos')
        try:
            for f in files[:20]:
                AvaliacaoFoto.objects.create(avaliacao=self.object, foto=f)
        except Exception as e:
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


# 3. CRIE A VIEW PARA EXCLUIR A AVALIAÇÃO
class AvaliacaoDeleteView(LoginRequiredMixin, DeleteView):
    model = Avaliacao
    template_name = 'avaliacoes/avaliacao_confirm_delete.html' # Template de confirmação
    success_url = reverse_lazy('avaliacao_list') # Para onde redirecionar após excluir

    def dispatch(self, request, *args, **kwargs):
        # Garante que apenas superusuários possam acessar esta view
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


# --- Views da API FIPE ---
def get_fipe_marcas(request):
    try:
        response = requests.get('https://parallelum.com.br/fipe/api/v1/carros/marcas')
        response.raise_for_status()
        return JsonResponse(response.json(), safe=False)
    except requests.RequestException:
        return JsonResponse({'error': 'Erro ao buscar marcas'}, status=500)

def get_fipe_modelos(request, marca_id):
    try:
        response = requests.get(f'https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos')
        response.raise_for_status()
        return JsonResponse(response.json().get('modelos', []), safe=False)
    except requests.RequestException:
        return JsonResponse({'error': 'Erro ao buscar modelos'}, status=500)

def get_fipe_anos(request, marca_id, modelo_id):
    try:
        response = requests.get(f'https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos')
        response.raise_for_status()
        return JsonResponse(response.json(), safe=False)
    except requests.RequestException:
        return JsonResponse({'error': 'Erro ao buscar anos'}, status=500)