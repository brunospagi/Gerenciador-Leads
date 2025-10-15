from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import CustomPasswordChangeForm, UserCreationFormByAdmin, UserUpdateFormByAdmin, AdminSetPasswordForm
from django.contrib.auth.models import User
from .models import Profile, UserLoginActivity
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
import json


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or (hasattr(self.request.user, 'profile') and self.request.user.profile.nivel_acesso == Profile.NivelAcesso.ADMIN)

@login_required
def profile_view(request):
    return render(request, 'usuarios/profile.html')

class CustomPasswordChangeView(PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'usuarios/password_change.html'
    success_url = reverse_lazy('profile')

    def form_valid(self, form):
        messages.success(self.request, 'Sua senha foi alterada com sucesso!')
        return super().form_valid(form)

class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'usuarios/user_list.html'
    context_object_name = 'usuarios'

class UserCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreationFormByAdmin
    template_name = 'usuarios/user_form.html'
    success_url = reverse_lazy('user_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Criar Novo Usuário"
        return context

class UserUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateFormByAdmin
    template_name = 'usuarios/user_form.html'
    success_url = reverse_lazy('user_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Editar Usuário"
        return context

class UserDeleteView(AdminRequiredMixin, DeleteView):
    model = User
    template_name = 'usuarios/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')


class UserPasswordChangeView(AdminRequiredMixin, FormView):
    form_class = AdminSetPasswordForm
    template_name = 'usuarios/user_password_change.html'
    success_url = reverse_lazy('user_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = User.objects.get(pk=self.kwargs['pk'])
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, f"A senha para o usuário '{form.user.username}' foi alterada com sucesso.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['target_user'] = User.objects.get(pk=self.kwargs['pk'])
        return context


# --- VIEW DO PAINEL DO ADMIN CORRIGIDA ---
@login_required
def admin_dashboard_view(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.nivel_acesso == 'ADMIN')):
        raise PermissionDenied("Você não tem permissão para acessar esta página.")

    # 1. Gráfico de logins nos últimos 15 dias
    start_date = timezone.now().date() - timedelta(days=14)
    
    # Consulta moderna e segura para agrupar logins por dia
    logins_por_dia = UserLoginActivity.objects.filter(
        login_timestamp__date__gte=start_date
    ).annotate(
        dia=TruncDate('login_timestamp')
    ).values('dia').annotate(
        total=Count('id')
    ).order_by('dia')

    # Mapeia os resultados para uma busca mais fácil
    logins_map = {item['dia'].strftime('%d/%m'): item['total'] for item in logins_por_dia}

    # Gera os dados para o gráfico, preenchendo dias sem login com 0
    dias_grafico = [(start_date + timedelta(days=i)).strftime('%d/%m') for i in range(15)]
    logins_grafico = [logins_map.get(dia, 0) for dia in dias_grafico]

    # 2. Usuários mais ativos (top 5)
    usuarios_ativos = User.objects.annotate(
        total_logins=Count('login_activities')
    ).filter(total_logins__gt=0).order_by('-total_logins')[:5]

    # 3. Últimos 10 logins
    ultimos_logins = UserLoginActivity.objects.select_related('user').all()[:10]

    context = {
        'labels_grafico': json.dumps(dias_grafico),
        'data_grafico': json.dumps(logins_grafico),
        'usuarios_ativos': usuarios_ativos,
        'ultimos_logins': ultimos_logins,
    }
    return render(request, 'usuarios/admin_dashboard.html', context)