import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, TemplateView, UpdateView

from .forms import FichaForm
from .models import Ficha

logger = logging.getLogger(__name__)


class KanbanView(LoginRequiredMixin, TemplateView):
    template_name = 'financiamentos/kanban.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
            qs = Ficha.objects.all()
        else:
            qs = Ficha.objects.filter(vendedor=user)

        colunas = [
            {'code': 'NOVA', 'label': 'Nova', 'color': 'secondary'},
            {'code': 'EM_ANALISE', 'label': 'Em Analise', 'color': 'info'},
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

            kanban_data.append(
                {
                    'code': col['code'],
                    'label': col['label'],
                    'color': col['color'],
                    'items': items,
                    'count': items.count(),
                    'total_retorno': total_retorno,
                }
            )

        context['kanban_data'] = kanban_data
        return context


class FichaCreateView(LoginRequiredMixin, CreateView):
    model = Ficha
    form_class = FichaForm
    template_name = 'financiamentos/form.html'
    success_url = reverse_lazy('financiamentos_kanban')

    def form_valid(self, form):
        form.instance.vendedor = self.request.user
        messages.success(self.request, 'Ficha cadastrada com sucesso!')
        return super().form_valid(form)


class FichaUpdateView(LoginRequiredMixin, UpdateView):
    model = Ficha
    form_class = FichaForm
    template_name = 'financiamentos/form.html'
    success_url = reverse_lazy('financiamentos_kanban')

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN':
            return Ficha.objects.all()
        return Ficha.objects.filter(vendedor=user)


@login_required
@require_POST
def update_ficha_status(request):
    try:
        data = json.loads(request.body)
        ficha_id = data.get('id')
        new_status = data.get('status')

        if not ficha_id or not new_status:
            return JsonResponse({'error': 'Dados obrigatorios ausentes.'}, status=400)

        status_validos = {code for code, _label in Ficha.STATUS_CHOICES}
        if new_status not in status_validos:
            return JsonResponse({'error': 'Status invalido.'}, status=400)

        ficha = get_object_or_404(Ficha, id=ficha_id)

        user = request.user
        if not (user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN'):
            if ficha.vendedor != user:
                return JsonResponse({'error': 'Permissao negada.'}, status=403)

        ficha.status = new_status
        ficha.save(update_fields=['status'])
        return JsonResponse({'success': True})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Corpo da requisicao invalido (JSON).'}, status=400)
    except Exception as exc:
        logger.exception('Erro ao atualizar status da ficha: %s', exc)
        return JsonResponse({'error': 'Erro interno ao atualizar status.'}, status=500)
