from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from .models import Avaliacao, AvaliacaoFoto
# CORREÇÃO: Importar os formulários atualizados
from .forms import AvaliacaoForm, FotoUploadForm
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import timedelta
from django.utils import timezone

class AvaliacaoListView(LoginRequiredMixin, ListView):
    model = Avaliacao
    template_name = 'avaliacoes/avaliacao_list.html'
    context_object_name = 'avaliacoes'

    def get_queryset(self):
        return Avaliacao.objects.filter(
            status='disponivel',
            data_criacao__gte=timezone.now() - timedelta(days=30)
        ).order_by('-data_criacao')

class AvaliacaoCreateView(LoginRequiredMixin, CreateView):
    model = Avaliacao
    form_class = AvaliacaoForm
    template_name = 'avaliacoes/avaliacao_form.html'
    success_url = reverse_lazy('avaliacao_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # CORREÇÃO: Usar o novo FotoUploadForm
        context['foto_form'] = FotoUploadForm()
        return context

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        # CORREÇÃO: Instanciar o FotoUploadForm com os dados do POST
        foto_form = FotoUploadForm(request.POST, request.FILES)

        if form.is_valid() and foto_form.is_valid():
            return self.form_valid(form, foto_form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form, foto_form):
        self.object = form.save()
        files = self.request.FILES.getlist('fotos')

        # --- Bloco de diagnóstico ---
        storage_em_uso = AvaliacaoFoto._meta.get_field('foto').storage
        print("*************************************************")
        print(f"DIAGNÓSTICO: A classe de storage em uso é: {storage_em_uso.__class__}")
        print("*************************************************")
        # --- Fim do bloco de diagnóstico ---

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