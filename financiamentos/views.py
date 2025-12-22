from django.views.generic import TemplateView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.contrib import messages
import json

from .models import Ficha
from .forms import FichaForm

class KanbanView(LoginRequiredMixin, TemplateView):
    template_name = 'financiamentos/kanban.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Filtro de Permissão: Admin vê tudo, Vendedor vê o seu
        if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
            qs = Ficha.objects.all()
        else:
            qs = Ficha.objects.filter(vendedor=user)
        
        # Definição das Colunas na ordem correta
        colunas = [
            {'code': 'NOVA', 'label': 'Nova', 'color': 'secondary'},
            {'code': 'EM_ANALISE', 'label': 'Em Análise', 'color': 'info'},
            {'code': 'APROVADA', 'label': 'Aprovada', 'color': 'success'},
            {'code': 'EM_ASSINATURA', 'label': 'Em Assinatura', 'color': 'primary'},
            {'code': 'EM_PAGAMENTO', 'label': 'Em Pagamento', 'color': 'warning'},
            {'code': 'PAGO', 'label': 'Pago', 'color': 'success'},
            {'code': 'FINALIZADO', 'label': 'Finalizado', 'color': 'dark'},
            {'code': 'RECUSADA', 'label': 'Recusada', 'color': 'danger'},
            {'code': 'CANCELADA', 'label': 'Cancelada', 'color': 'danger'},
        ]
        
        kanban_data = []
        for col in colunas:
            items = qs.filter(status=col['code'])
            total_retorno = items.aggregate(Sum('valor_retorno'))['valor_retorno__sum'] or 0
            
            kanban_data.append({
                'code': col['code'],
                'label': col['label'],
                'color': col['color'],
                'items': items,
                'count': items.count(),
                'total_retorno': total_retorno
            })
            
        context['kanban_data'] = kanban_data
        return context

class FichaCreateView(LoginRequiredMixin, CreateView):
    model = Ficha
    form_class = FichaForm
    template_name = 'financiamentos/form.html'
    success_url = reverse_lazy('financiamentos_kanban')

    def form_valid(self, form):
        form.instance.vendedor = self.request.user
        messages.success(self.request, "Ficha cadastrada com sucesso!")
        return super().form_valid(form)

class FichaUpdateView(LoginRequiredMixin, UpdateView):
    model = Ficha
    form_class = FichaForm
    template_name = 'financiamentos/form.html'
    success_url = reverse_lazy('financiamentos_kanban')
    
    def get_queryset(self):
        # Garante que vendedor só edita o que é dele (exceto Admin)
        user = self.request.user
        if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
            return Ficha.objects.all()
        return Ficha.objects.filter(vendedor=user)

# API AJAX para Drag & Drop
def update_ficha_status(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            ficha_id = data.get('id')
            new_status = data.get('status')
            
            ficha = get_object_or_404(Ficha, id=ficha_id)
            
            # Verificação de segurança
            user = request.user
            if not (user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN'):
                if ficha.vendedor != user:
                    return JsonResponse({'error': 'Permissão negada'}, status=403)
            
            ficha.status = new_status
            ficha.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Método inválido'}, status=400)