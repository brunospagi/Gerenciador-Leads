from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import redirect

from .resolver import has_module_action


def _is_ajax_ou_json(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.headers.get('Accept', '').startswith('application/json')
        or request.content_type == 'application/json'
    )


class ModuleActionRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin genérico pra CBVs: exige `module_action` (visualizar/criar/editar/excluir) no `module_key`."""

    module_key = None
    module_action = 'visualizar'

    def test_func(self):
        return has_module_action(self.request.user, self.module_key, self.module_action)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            if _is_ajax_ou_json(self.request):
                return JsonResponse({'error': 'Permissao negada.'}, status=403)
            messages.error(self.request, "Você não tem permissão para esta ação.")
            return redirect('portal')
        return super().handle_no_permission()


def require_module_action(module_key, action):
    """Decorator equivalente pra FBVs (inclusive endpoints AJAX/JSON, que recebem 403 em vez de redirect)."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not has_module_action(request.user, module_key, action):
                if _is_ajax_ou_json(request):
                    return JsonResponse({'error': 'Permissao negada.'}, status=403)
                messages.error(request, "Você não tem permissão para esta ação.")
                return redirect('portal')
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
