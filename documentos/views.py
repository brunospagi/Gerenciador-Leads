from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import Procuracao, Outorgado # Importar Outorgado
from .forms import ProcuracaoForm, OutorgadoForm # Importar OutorgadoForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.utils.text import slugify

# --- Mixin para restringir acesso apenas a Admins ---
class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        # Verifica se é superuser OU se tem perfil de ADMIN
        return self.request.user.is_superuser or \
               (hasattr(self.request.user, 'profile') and self.request.user.profile.nivel_acesso == 'ADMIN')

    def handle_no_permission(self):
        # Se não tiver permissão, levanta erro 403
        raise PermissionDenied("Acesso restrito a Administradores.")

# --- Novas Views para Gerenciar Outorgados (Apenas Admins) ---

class OutorgadoListView(AdminRequiredMixin, ListView):
    model = Outorgado
    template_name = 'documentos/outorgado_list.html'
    context_object_name = 'outorgados'

class OutorgadoCreateView(AdminRequiredMixin, CreateView):
    model = Outorgado
    form_class = OutorgadoForm
    template_name = 'documentos/outorgado_form.html'
    success_url = reverse_lazy('outorgado_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Adicionar Novo Outorgado"
        return context

class OutorgadoUpdateView(AdminRequiredMixin, UpdateView):
    model = Outorgado
    form_class = OutorgadoForm
    template_name = 'documentos/outorgado_form.html'
    success_url = reverse_lazy('outorgado_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Editar Outorgado"
        return context

class OutorgadoDeleteView(AdminRequiredMixin, DeleteView):
    model = Outorgado
    template_name = 'documentos/outorgado_confirm_delete.html'
    success_url = reverse_lazy('outorgado_list')


# --- Views de Procuração (Existentes) ---

class ProcuracaoListView(LoginRequiredMixin, ListView):
    model = Procuracao
    template_name = 'documentos/procuracao_list.html'
    context_object_name = 'procuracoes'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or (hasattr(user, 'profile') and user.profile.nivel_acesso == 'ADMIN'):
            return Procuracao.objects.all()
        return Procuracao.objects.filter(vendedor=user)

class ProcuracaoCreateView(LoginRequiredMixin, CreateView):
    model = Procuracao
    form_class = ProcuracaoForm
    template_name = 'documentos/procuracao_form.html'
    success_url = reverse_lazy('procuracao_list')

    def form_valid(self, form):
        form.instance.vendedor = self.request.user
        return super().form_valid(form)

class ProcuracaoUpdateView(LoginRequiredMixin, UpdateView):
    model = Procuracao
    form_class = ProcuracaoForm
    template_name = 'documentos/procuracao_form.html'
    success_url = reverse_lazy('procuracao_list')

    def get_object(self, *args, **kwargs):
        obj = super().get_object(*args, **kwargs)
        user = self.request.user
        if not user.is_superuser and obj.vendedor != user:
            raise PermissionDenied("Você não tem permissão para editar este documento.")
        return obj

class ProcuracaoDeleteView(LoginRequiredMixin, DeleteView):
    model = Procuracao
    template_name = 'documentos/procuracao_confirm_delete.html'
    success_url = reverse_lazy('procuracao_list')

    def get_object(self, *args, **kwargs):
        obj = super().get_object(*args, **kwargs)
        user = self.request.user
        if not user.is_superuser and obj.vendedor != user:
            raise PermissionDenied("Você não tem permissão para excluir este documento.")
        return obj

# --- View de Geração de PDF (MODIFICADA) ---

def gerar_procuracao_pdf(request, pk):
    """
    Gera o PDF da procuração com base no template e nos dados do objeto.
    """
    procuracao = get_object_or_404(Procuracao, pk=pk)
    
    # Verifica permissão
    user = request.user
    if not user.is_superuser and procuracao.vendedor != user:
        raise PermissionDenied("Você não tem permissão para gerar este PDF.")

    template_path = 'documentos/procuracao_pdf_template.html'
    
    # --- ALTERAÇÃO AQUI ---
    # Busca a lista de outorgados do banco de dados
    outorgados_list = Outorgado.objects.all().order_by('nome')
    
    # Define a cidade fixa e a data de geração
    context = {
        'procuracao': procuracao,
        'outorgados': outorgados_list, # Passa a lista para o template
        'cidade': 'São José dos Pinhais', # Fixo, conforme solicitado
        'data_hoje': timezone.now()
    }
    
    template = get_template(template_path)
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    filename = f"procuracao-{slugify(procuracao.veiculo_placa)}-{slugify(procuracao.outorgante_nome)}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Converte HTML para PDF
    pisa_status = pisa.CreatePDF(
       html, dest=response, encoding='UTF-8')

    if pisa_status.err:
       return HttpResponse('Ocorreram erros ao gerar o PDF <pre>' + html + '</pre>')
    return response