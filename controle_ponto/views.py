from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import RegistroPonto
from funcionarios.models import Funcionario

# === CONFIGURAÇÃO DO IP PERMITIDO ===
IP_PERMITIDO_LOJA = '187.19.123.45' 

def obter_ip_cliente(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

@login_required
def relogio_ponto(request):
    # --- CORREÇÃO AQUI: Busca direta e segura ---
    # Em vez de request.user.funcionario, usamos o .filter() que nunca dá erro de atributo.
    funcionario = Funcionario.objects.filter(user=request.user).first()
    
    if not funcionario:
        messages.error(request, "Acesso Negado: O seu utilizador não está associado a uma ficha de Funcionário no RH.")
        return redirect('/') # Volta para a home/dashboard

    ip_atual = obter_ip_cliente(request)
    hoje = timezone.now().date()
    agora = timezone.now().time()
    
    # --- BLOQUEIO POR IP (Descomente quando for para produção) ---
    # if IP_PERMITIDO_LOJA != '*' and ip_atual != IP_PERMITIDO_LOJA:
    #     messages.error(request, f"Ponto bloqueado! Você precisa estar no Wi-Fi da loja para registrar o ponto. (Seu IP: {ip_atual})")
    #     return redirect('/')

    ponto, created = RegistroPonto.objects.get_or_create(funcionario=funcionario, data=hoje)

    if request.method == 'POST':
        tipo_batida = request.POST.get('tipo_batida')
        foto_base64 = request.POST.get('foto_base64')
        
        if not foto_base64:
            messages.error(request, "Falha ao receber a foto. Tente novamente.")
            return redirect('controle_ponto:relogio')

        if tipo_batida == 'entrada' and not ponto.entrada:
            ponto.entrada = agora
            ponto.foto_entrada = foto_base64
            ponto.ip_registrado = ip_atual
            messages.success(request, f"Entrada registrada: {agora.strftime('%H:%M')}")
            
        elif tipo_batida == 'saida_almoco' and not ponto.saida_almoco:
            ponto.saida_almoco = agora
            ponto.foto_saida_almoco = foto_base64
            messages.success(request, f"Saída para almoço: {agora.strftime('%H:%M')}")
            
        elif tipo_batida == 'retorno_almoco' and not ponto.retorno_almoco:
            ponto.retorno_almoco = agora
            ponto.foto_retorno_almoco = foto_base64
            messages.success(request, f"Retorno do almoço: {agora.strftime('%H:%M')}")
            
        elif tipo_batida == 'saida' and not ponto.saida:
            ponto.saida = agora
            ponto.foto_saida = foto_base64
            messages.success(request, f"Fim de expediente: {agora.strftime('%H:%M')}. Bom descanso!")
        else:
            messages.warning(request, "Batida inválida ou já registrada.")

        ponto.save()
        return redirect('controle_ponto:relogio')
    # Pegamos a URL da foto de cadastro do funcionário para a IA usar como base
    foto_url = funcionario.foto_biometria.url if funcionario.foto_biometria else None

    return render(request, 'controle_ponto/relogio.html', {
        'ponto': ponto,
        'ip_atual': ip_atual,
        'foto_url': foto_url,
    })