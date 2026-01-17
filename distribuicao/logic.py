# distribuicao/logic.py
from django.utils import timezone
from .models import VendedorRodizio
import requests
import json

# URL do seu Webhook N8N (Coloque no .env em produção)
N8N_WEBHOOK_URL = "SEU_LINK_DO_N8N_AQUI" 

def definir_proximo_vendedor():
    """
    Retorna o objeto User do próximo vendedor da fila e atualiza o horário dele.
    """
    # Pega o vendedor ativo que recebeu lead há mais tempo (ou nunca recebeu)
    proximo = VendedorRodizio.objects.filter(ativo=True).order_by('ultima_atribuicao').first()
    
    if not proximo:
        # Fallback: Se não tiver ninguém no rodízio, retorna o primeiro superusuário ou lança erro
        from django.contrib.auth.models import User
        return User.objects.filter(is_superuser=True).first()

    # Atualiza o horário dele para ir para o fim da fila
    proximo.ultima_atribuicao = timezone.now()
    proximo.save()
    
    return proximo.vendedor

def enviar_webhook_n8n(cliente):
    """
    Envia os dados do lead para o n8n via POST.
    """
    payload = {
        "id": cliente.id,
        "nome": cliente.nome_cliente,
        "telefone": cliente.whatsapp,
        "veiculo_interesse": cliente.modelo_veiculo, # Ajustado para seu modelo
        "canal_origem": cliente.fonte_cliente,     # Ajustado para seu modelo
        "vendedor_atribuido": cliente.vendedor.username,
        "data_entrada": cliente.data_primeiro_contato.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        requests.post(N8N_WEBHOOK_URL, json=payload, timeout=2)
    except Exception as e:
        print(f"[ERRO Webhook] Falha ao enviar para n8n: {e}")