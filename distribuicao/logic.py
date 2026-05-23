from django.utils import timezone
from django.db.models import F
from .models import VendedorRodizio
import requests
import os

# ADICIONE A URL DO SEU WEBHOOK AQUI
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "https://seu-n8n-webhook-url-aqui") 

def definir_proximo_vendedor():
    """
    Retorna o User do próximo vendedor e atualiza o timestamp dele.
    Lógica:
    1. Filtra apenas ATIVOS.
    2. Filtra apenas quem bateu ponto de ENTRADA no dia.
    2. Ordena colocando quem tem data NULL (nunca recebeu) no topo.
    3. Depois ordena por quem recebeu há mais tempo.
    """
    hoje = timezone.localdate()
    proximo = VendedorRodizio.objects.filter(
        ativo=True,
        vendedor__dados_funcionais__ativo=True,
        vendedor__dados_funcionais__pontos__data=hoje,
        vendedor__dados_funcionais__pontos__entrada__isnull=False,
    ).order_by(
        F('ultima_atribuicao').asc(nulls_first=True), 
        'ordem'
    ).distinct().first()
    
    if not proximo:
        return None

    # Atualiza o horário para o momento atual (fim da fila)
    proximo.ultima_atribuicao = timezone.now()
    proximo.save()
    
    return proximo.vendedor

def enviar_webhook_n8n(cliente):
    """Envia dados do lead para o n8n."""
    payload = {
        "id": cliente.id,
        "nome": cliente.nome_cliente,
        "telefone": cliente.whatsapp,
        "veiculo_interesse": cliente.modelo_veiculo,
        "canal_origem": cliente.fonte_cliente,
        "vendedor_atribuido": cliente.vendedor.username if cliente.vendedor else "N/A",
        "data_entrada": cliente.data_primeiro_contato.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        # Timeout curto para não travar o painel se o n8n demorar
        requests.post(N8N_WEBHOOK_URL, json=payload, timeout=2)
    except Exception as e:
        print(f"[ALERTA] Falha no Webhook n8n: {e}")
