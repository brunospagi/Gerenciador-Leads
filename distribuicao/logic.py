from datetime import datetime, time

from django.utils import timezone

from .models import VendedorRodizio
from controle_ponto.models import RegistroPonto
import requests
import os

# ADICIONE A URL DO SEU WEBHOOK AQUI
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "https://seu-n8n-webhook-url-aqui")


def _listar_vendedores_disponiveis(agora_local=None):
    """Retorna lista de objetos VendedorRodizio elegiveis no rodizio."""
    hoje = timezone.localdate()
    agora_local = agora_local or timezone.localtime()
    hora_atual = agora_local.time()

    candidatos = list(
        VendedorRodizio.objects.filter(ativo=True).select_related('vendedor', 'vendedor__dados_funcionais')
    )
    candidatos.sort(
        key=lambda item: (
            item.ultima_atribuicao is not None,
            item.ultima_atribuicao or datetime.min,
            item.ordem,
        )
    )

    elegiveis = []
    for candidato in candidatos:
        funcionario = getattr(candidato.vendedor, 'dados_funcionais', None)
        if not funcionario:
            continue

        ponto_hoje = (
            RegistroPonto.objects.filter(funcionario=funcionario, data=hoje)
            .only('entrada', 'saida_almoco', 'retorno_almoco')
            .first()
        )
        if not ponto_hoje or not ponto_hoje.entrada:
            continue

        # No almoço: saiu e ainda não retornou -> bloqueado.
        if ponto_hoje.saida_almoco and not ponto_hoje.retorno_almoco:
            continue

        # Até 13:59 livre sem saída de almoço; após 14:00 precisa ter saída.
        if hora_atual >= time(14, 0) and not ponto_hoje.saida_almoco:
            continue

        elegiveis.append(candidato)

    return elegiveis


def vendedor_disponivel_no_rodizio(vendedor, agora_local=None):
    return any(item.vendedor_id == vendedor.id for item in _listar_vendedores_disponiveis(agora_local=agora_local))


def definir_proximo_vendedor():
    """
    Retorna o User do proximo vendedor e atualiza o timestamp dele.
    """
    vendedores_elegiveis = _listar_vendedores_disponiveis()
    proximo = vendedores_elegiveis[0] if vendedores_elegiveis else None

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
