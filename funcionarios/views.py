from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .forms import UserRegistrationForm, FuncionarioForm
from .models import Funcionario

# === PERMISSÃO: ADMIN OU GERENTE (Gestão de Pessoas) ===
def is_gestor_pessoal(user):
    if user.is_superuser: return True
    nivel = getattr(user.profile, 'nivel_acesso', '')
    return nivel in ['ADMIN', 'GERENTE']

@login_required
@user_passes_test(is_gestor_pessoal)
def lista_funcionarios(request):
    """View exclusiva para Gerentes verem a equipe sem acessar financeiro"""
    funcionarios = Funcionario.objects.filter(ativo=True)
    return render(request, 'funcionarios/lista_colaboradores.html', {
        'funcionarios': funcionarios
    })

@login_required
@user_passes_test(is_gestor_pessoal)
def cadastrar_funcionario(request):
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        # O FuncionarioForm processa dados do POST (o vinculo com user é feito após salvar user)
        
        if user_form.is_valid():
            # 1. Salva User
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.save()
            
            # 2. Atualiza Perfil (Criado pelo Signal)
            if hasattr(user, 'dados_funcionais'):
                funcionario = user.dados_funcionais
                func_form = FuncionarioForm(request.POST, instance=funcionario)
            else:
                func_form = FuncionarioForm(request.POST)
                funcionario = func_form.save(commit=False)
                funcionario.user = user

            if func_form.is_valid():
                func_form.save()
                messages.success(request, f"Colaborador {user.get_full_name()} cadastrado!")
                
                # REDIRECIONAMENTO INTELIGENTE
                # Se for ADMIN -> Vai para o Dashboard Financeiro
                if request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN':
                    return redirect('rh_dashboard')
                # Se for GERENTE -> Vai para a Lista Simples
                else:
                    return redirect('lista_funcionarios')
            else:
                user.delete() # Rollback manual
                messages.error(request, "Erro nos dados funcionais.")
        else:
            func_form = FuncionarioForm(request.POST) # Para renderizar erros
            messages.error(request, "Erro nos dados de login.")
    else:
        user_form = UserRegistrationForm()
        func_form = FuncionarioForm()
    
    # Define para onde o botão "Voltar" aponta
    back_url = 'rh_dashboard' if (request.user.is_superuser or getattr(request.user.profile, 'nivel_acesso', '') == 'ADMIN') else 'lista_funcionarios'

    return render(request, 'funcionarios/cadastro_funcionario.html', {
        'user_form': user_form,
        'func_form': func_form,
        'back_url': back_url
    })