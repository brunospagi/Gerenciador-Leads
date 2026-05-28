from datetime import time

from django.db.models import F, Q
from django.utils import timezone

from .models import VendedorRodizio
import requests
import os

# ADICIONE A URL DO SEU WEBHOOK AQUI
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "https://seu-n8n-webhook-url-aqui")


def _queryset_vendedores_disponiveis(agora_local=None):
    """Retorna queryset de vendedores elegiveis para receber lead no rodizio."""
    hoje = timezone.localdate()
    agora_local = agora_local or timezone.localtime()
    hora_atual = agora_local.time()

    vendedores_disponiveis = VendedorRodizio.objects.filter(
        ativo=True,
        vendedor__dados_funcionais__ativo=True,
        vendedor__dados_funcionais__pontos__data=hoje,
        vendedor__dados_funcionais__pontos__entrada__isnull=False,
    ).exclude(
        Q(vendedor__dados_funcionais__pontos__data=hoje)
        & Q(vendedor__dados_funcionais__pontos__saida_almoco__isnull=False)
        & Q(vendedor__dados_funcionais__pontos__retorno_almoco__isnull=True)
    )

    # Ate 14:00 fica livre mesmo sem saida de almoco.
    # Apos 14:00, exige saida_almoco registrada.
    if hora_atual >= time(14, 0):
        vendedores_disponiveis = vendedores_disponiveis.filter(
            vendedor__dados_funcionais__pontos__saida_almoco__isnull=False,
        )

    return vendedores_disponiveis.distinct()


def vendedor_disponivel_no_rodizio(vendedor, agora_local=None):
    return _queryset_vendedores_disponiveis(agora_local=agora_local).filter(vendedor=vendedor).exists()


def definir_proximo_vendedor():
    """
    Retorna o User do proximo vendedor e atualiza o timestamp dele.
    """
    proximo = _queryset_vendedores_disponiveis().order_by(
        F('ultima_atribuicao').asc(nulls_first=True),
        'ordem'
    ).first()

    if not proximo:
        return None

    # Atualiza o horario para o momento atual (fim da fila)
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
        # Timeout curto para nao travar o painel se o n8n demorar
        requests.post(N8N_WEBHOOK_URL, json=payload, timeout=2)
    except Exception as e:
        print(f"[ALERTA] Falha no Webhook n8n: {e}")
