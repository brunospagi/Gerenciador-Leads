from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import Procuracao, Outorgado 
from .forms import ProcuracaoForm, OutorgadoForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.utils.text import slugify
import os
from django.conf import settings
from urllib.parse import urlparse
from django.contrib.staticfiles import finders


# --- Mixin para restringir acesso apenas a Admins ---
class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or \
               (hasattr(self.request.user, 'profile') and self.request.user.profile.nivel_acesso == 'ADMIN')

    def handle_no_permission(self):
        raise PermissionDenied("Acesso restrito a Administradores.")

# --- Views para Gerenciar Outorgados (Apenas Admins) ---

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

# --- FUNÇÃO link_callback (ATUALIZADA) ---
def link_callback(uri, rel):
    """
    Converte um URI de HTML (como /static/images/logo.png ou http://.../static/...)
    para um caminho absoluto no sistema de arquivos.
    """
    try:
        # 1. Analisa a URL
        parsed_uri = urlparse(uri)
        
        # 2. Obtém o caminho (ex: /static/images/detran_logo.png)
        # Se for uma URL absoluta, isso remove o 'http://dominio.com'
        path = parsed_uri.path
        
        # 3. Remove o STATIC_URL do início do caminho
        # (ex: remove /static/ deixando 'images/detran_logo.png')
        if path.startswith(settings.STATIC_URL):
            path = path[len(settings.STATIC_URL):]
        
        # 4. Usa o 'finders' do Django para encontrar o caminho absoluto no sistema
        # Isso procura em STATIC_ROOT e em todas as pastas 'static' dos apps
        result = finders.find(path)
        
        # 5. Se não encontrar, tenta o caminho original (fallback)
        if not result:
            result = os.path.join(settings.STATIC_ROOT, path)

        # 6. Verifica se o arquivo realmente existe
        if not os.path.isfile(result):
            print(f"Erro no link_callback: Não foi possível encontrar o arquivo para o URI: {uri}")
            print(f"Caminho procurado: {result}")
            return None
            
        return result
    except Exception as e:
        print(f"Exceção no link_callback: {e} - URI: {uri}")
        return None


# --- View de Geração de PDF (ATUALIZADA) ---

def gerar_procuracao_pdf(request, pk):
    procuracao = get_object_or_404(Procuracao, pk=pk)
    
    user = request.user
    if not user.is_superuser and procuracao.vendedor != user:
        raise PermissionDenied("Você não tem permissão para gerar este PDF.")

    template_path = 'documentos/procuracao_pdf_template.html'
    
    outorgados_list = Outorgado.objects.all().order_by('nome')
    
    context = {
        'procuracao': procuracao,
        'outorgados': outorgados_list,
        'cidade': 'São José dos Pinhais', 
        'data_hoje': timezone.now(),
        'STATIC_URL': settings.STATIC_URL,
    }
    
    template = get_template(template_path)
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    filename = f"procuracao-{slugify(procuracao.veiculo_placa)}-{slugify(procuracao.outorgante_nome)}.pdf"

    # --- AQUI ESTÁ A MUDANÇA ---
    # Verificamos se o usuário quer 'imprimir' (inline) ou 'baixar' (attachment)
    target = request.GET.get('target')
    if target == 'inline':
        # Abre o PDF no navegador
        response['Content-Disposition'] = f'inline; filename="{filename}"'
    else:
        # Força o download do PDF
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    # --- FIM DA MUDANÇA ---

    pisa_status = pisa.CreatePDF(
       html, 
       dest=response, 
       encoding='UTF-8',
       link_callback=link_callback
    )

    if pisa_status.err:
       return HttpResponse('Ocorreram erros ao gerar o PDF <pre>' + html + '</pre>')
    return response