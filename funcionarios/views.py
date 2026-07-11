from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from configuracoes.access import require_module_action
from .forms import FuncionarioForm, UserRegistrationForm, UserUpdateForm
from .models import Funcionario


def is_gestor_pessoal(user):
    if user.is_superuser:
        return True
    nivel = getattr(user.profile, 'nivel_acesso', '')
    return nivel in ['ADMIN', 'GERENTE']


def _rh_back_url(user):
    return 'rh_dashboard' if (user.is_superuser or getattr(user.profile, 'nivel_acesso', '') == 'ADMIN') else 'lista_funcionarios'


@require_module_action('rh', 'visualizar')
@user_passes_test(is_gestor_pessoal)
def lista_funcionarios(request):
    """Gestão de equipe com visão ativa/inativa e filtros."""
    status = (request.GET.get('status') or 'ativos').strip().lower()
    q = (request.GET.get('q') or '').strip()

    qs_base = Funcionario.objects.select_related('user').order_by('user__first_name', 'user__last_name')

    if status == 'inativos':
        funcionarios = qs_base.filter(ativo=False)
    elif status == 'todos':
        funcionarios = qs_base
    else:
        status = 'ativos'
        funcionarios = qs_base.filter(ativo=True)

    if q:
        funcionarios = funcionarios.filter(
            Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__email__icontains=q)
            | Q(cargo__icontains=q)
            | Q(cpf__icontains=q)
        )

    total_colaboradores = qs_base.count()
    total_ativos = qs_base.filter(ativo=True).count()
    total_inativos = qs_base.filter(ativo=False).count()

    return render(
        request,
        'funcionarios/lista_colaboradores.html',
        {
            'funcionarios': funcionarios,
            'filtro_status': status,
            'busca': q,
            'total_colaboradores': total_colaboradores,
            'total_ativos': total_ativos,
            'total_inativos': total_inativos,
        },
    )


@require_module_action('rh', 'criar')
@user_passes_test(is_gestor_pessoal)
def cadastrar_funcionario(request):
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        func_form = FuncionarioForm(request.POST, request.FILES)

        if user_form.is_valid() and func_form.is_valid():
            with transaction.atomic():
                user = user_form.save(commit=False)
                user.set_password(user_form.cleaned_data['password'])

                # Evita perfil funcional automático durante cadastro manual do RH.
                user._skip_funcionario_signal = True
                user.save()

                funcionario = func_form.save(commit=False)
                funcionario.user = user
                funcionario.save()

            messages.success(request, f'Colaborador {user.get_full_name() or user.username} cadastrado com sucesso.')
            return redirect(_rh_back_url(request.user))

        messages.error(request, 'Verifique os dados informados e tente novamente.')
    else:
        user_form = UserRegistrationForm()
        func_form = FuncionarioForm()

    return render(
        request,
        'funcionarios/cadastro_funcionario.html',
        {
            'user_form': user_form,
            'func_form': func_form,
            'back_url': _rh_back_url(request.user),
            'is_edit': False,
            'page_title': 'Cadastro de Colaborador',
            'submit_label': 'Salvar Cadastro',
        },
    )


@require_module_action('rh', 'editar')
@user_passes_test(is_gestor_pessoal)
def editar_funcionario(request, pk):
    funcionario = get_object_or_404(Funcionario.objects.select_related('user'), pk=pk)
    user = funcionario.user

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        func_form = FuncionarioForm(request.POST, request.FILES, instance=funcionario)

        if user_form.is_valid() and func_form.is_valid():
            user_form.save()
            func_form.save()
            messages.success(request, f'Cadastro de {funcionario.nome_completo} atualizado com sucesso.')
            return redirect('lista_funcionarios')

        messages.error(request, 'Verifique os dados informados e tente novamente.')
    else:
        user_form = UserUpdateForm(instance=user)
        func_form = FuncionarioForm(instance=funcionario)

    return render(
        request,
        'funcionarios/cadastro_funcionario.html',
        {
            'user_form': user_form,
            'func_form': func_form,
            'back_url': 'lista_funcionarios',
            'is_edit': True,
            'page_title': f'Editar Colaborador: {funcionario.nome_completo}',
            'submit_label': 'Salvar Alterações',
            'funcionario_obj': funcionario,
        },
    )
