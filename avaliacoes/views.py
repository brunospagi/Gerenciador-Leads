from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from .models import Avaliacao, AvaliacaoFoto
from .forms import AvaliacaoForm, AvaliacaoFotoForm
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import timedelta
from django.utils import timezone

class AvaliacaoListView(LoginRequiredMixin, ListView):
    model = Avaliacao
    template_name = 'avaliacoes/avaliacao_list.html'
    context_object_name = 'avaliacoes'

    def get_queryset(self):
        # Filtra para mostrar apenas avaliações disponíveis e criadas nos últimos 30 dias
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
        if self.request.POST:
            context['foto_form'] = AvaliacaoFotoForm(self.request.POST, self.request.FILES)
        else:
            context['foto_form'] = AvaliacaoFotoForm()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        foto_form = context['foto_form']
        if foto_form.is_valid():
            self.object = form.save()
            files = self.request.FILES.getlist('foto')
            # Limita o upload a 20 fotos
            for f in files[:20]:
                AvaliacaoFoto.objects.create(avaliacao=self.object, foto=f)
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

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