import logging

from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import Procuracao, Outorgado
from .forms import ProcuracaoForm, OutorgadoForm, CRLVUploadForm
from .pdf_utils import extract_crlv_data_with_gemini as extract_crlv_data
from configuracoes.access import ModuleActionRequiredMixin, require_module_action
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.utils.text import slugify
import os
from django.conf import settings
from urllib.parse import urlparse
from django.contrib.staticfiles import finders
from django.contrib import messages

logger = logging.getLogger(__name__)


@require_module_action('documentos', 'criar')
@require_POST
def procuracao_extrair_crlv(request):
    """Extração via AJAX do CRLV-e, usada no formulário de nova procuração."""
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)

    upload_form = CRLVUploadForm(files={'crlv_pdf': arquivo})
    if not upload_form.is_valid():
        erros = upload_form.errors.get('crlv_pdf') or ['Arquivo inválido.']
        return JsonResponse({'erro': '; '.join(erros)}, status=400)

    dados = extract_crlv_data(upload_form.cleaned_data['crlv_pdf'])
    if not dados:
        return JsonResponse({'disponivel': False})

    return JsonResponse({'disponivel': True, 'dados': dados})


# --- Views para Gerenciar Outorgados ---

class OutorgadoListView(ModuleActionRequiredMixin, ListView):
    module_key = 'documentos'
    module_action = 'visualizar'
    model = Outorgado
    template_name = 'documentos/outorgado_list.html'
    context_object_name = 'outorgados'

class OutorgadoCreateView(ModuleActionRequiredMixin, CreateView):
    module_key = 'documentos'
    module_action = 'criar'
    model = Outorgado
    form_class = OutorgadoForm
    template_name = 'documentos/outorgado_form.html'
    success_url = reverse_lazy('outorgado_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Adicionar Novo Outorgado"
        return context

class OutorgadoUpdateView(ModuleActionRequiredMixin, UpdateView):
    module_key = 'documentos'
    module_action = 'editar'
    model = Outorgado
    form_class = OutorgadoForm
    template_name = 'documentos/outorgado_form.html'
    success_url = reverse_lazy('outorgado_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Editar Outorgado"
        return context

class OutorgadoDeleteView(ModuleActionRequiredMixin, DeleteView):
    module_key = 'documentos'
    module_action = 'excluir'
    model = Outorgado
    template_name = 'documentos/outorgado_confirm_delete.html'
    success_url = reverse_lazy('outorgado_list')


# --- Views de Procuração (Existentes) ---

class ProcuracaoListView(ModuleActionRequiredMixin, ListView):
    module_key = 'documentos'
    module_action = 'visualizar'
    model = Procuracao
    template_name = 'documentos/procuracao_list.html'
    context_object_name = 'procuracoes'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or (hasattr(user, 'profile') and user.profile.nivel_acesso == 'ADMIN'):
            return Procuracao.objects.all()
        return Procuracao.objects.filter(vendedor=user)

class ProcuracaoCreateView(ModuleActionRequiredMixin, CreateView):
    module_key = 'documentos'
    module_action = 'criar'
    model = Procuracao
    form_class = ProcuracaoForm
    template_name = 'documentos/procuracao_form.html'
    success_url = reverse_lazy('procuracao_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Gerar Nova Procuração"
        return context

    def form_valid(self, form):
        form.instance.vendedor = self.request.user
        messages.success(self.request, "Procuração salva com sucesso!")
        return super().form_valid(form)

class ProcuracaoUpdateView(ModuleActionRequiredMixin, UpdateView):
    module_key = 'documentos'
    module_action = 'editar'
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

class ProcuracaoDeleteView(ModuleActionRequiredMixin, DeleteView):
    module_key = 'documentos'
    module_action = 'excluir'
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
            logger.warning("link_callback: arquivo nao encontrado para URI=%s caminho=%s", uri, result)
            return None

        return result
    except Exception as e:
        logger.warning("Excecao no link_callback: %s - URI: %s", e, uri)
        return None


# --- View de Geração de PDF (ATUALIZADA) ---

@require_module_action('documentos', 'visualizar')
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