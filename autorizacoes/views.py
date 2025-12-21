from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from .models import Autorizacao
from .forms import AutorizacaoForm

# Lista de Autorizações (Vendedor vê as suas, Gerente vê todas ou filtra)
class AutorizacaoListView(LoginRequiredMixin, ListView):
    model = Autorizacao
    template_name = 'autorizacoes/lista.html'
    context_object_name = 'autorizacoes'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        # Se for Admin/Gerente vê tudo, se não, só as suas
        if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
            return Autorizacao.objects.all()
        return Autorizacao.objects.filter(vendedor=user)

# Criar Nova Solicitação
class AutorizacaoCreateView(LoginRequiredMixin, CreateView):
    model = Autorizacao
    form_class = AutorizacaoForm
    template_name = 'autorizacoes/form.html'
    success_url = reverse_lazy('autorizacao_list')

    def form_valid(self, form):
        form.instance.vendedor = self.request.user
        messages.success(self.request, "Solicitação de autorização criada com sucesso!")
        return super().form_valid(form)

# Visualização para Impressão (Sem menus, focada no papel)
class AutorizacaoPrintView(LoginRequiredMixin, DetailView):
    model = Autorizacao
    template_name = 'autorizacoes/print_document.html'
    context_object_name = 'item'

# Ação de Aprovar (Apenas Gerente/Admin)
def aprovar_autorizacao(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Verificação de segurança: Apenas Admin pode aprovar
    if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
        messages.error(request, "Você não tem permissão para aprovar.")
        return redirect('autorizacao_list')

    autorizacao = get_object_or_404(Autorizacao, pk=pk)
    autorizacao.status = 'APROVADO'
    autorizacao.gerente = request.user
    autorizacao.data_aprovacao = timezone.now()
    autorizacao.save()
    
    messages.success(request, f"Autorização {autorizacao.pk} APROVADA com sucesso.")
    return redirect('autorizacao_list')

# Ação de Rejeitar
def rejeitar_autorizacao(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN'):
        messages.error(request, "Você não tem permissão para rejeitar.")
        return redirect('autorizacao_list')

    autorizacao = get_object_or_404(Autorizacao, pk=pk)
    autorizacao.status = 'REJEITADO'
    autorizacao.gerente = request.user
    autorizacao.data_aprovacao = timezone.now()
    autorizacao.save()
    
    messages.warning(request, f"Autorização {autorizacao.pk} REJEITADA.")
    return redirect('autorizacao_list')