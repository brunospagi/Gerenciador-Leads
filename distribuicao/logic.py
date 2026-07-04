from datetime import datetime, time
import logging
import os
import re

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import VendedorRodizio
from controle_ponto.models import RegistroPonto


logger = logging.getLogger(__name__)

# ADICIONE A URL DO SEU WEBHOOK AQUI
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "https://seu-n8n-webhook-url-aqui")


def encontrar_cliente_por_whatsapp(whatsapp):
    """
    Procura um Cliente existente cujo whatsapp bata (por digitos) com o informado.
    Cliente.whatsapp e salvo com a formatacao digitada (nao normalizado), entao
    comparamos os digitos extraidos dos dois lados para evitar falso positivo/negativo
    por diferenca de formatacao.
    """
    from clientes.models import Cliente

    numeros = re.sub(r"\D", "", whatsapp or "")
    if not numeros:
        return None

    candidatos = Cliente.objects.exclude(whatsapp="").select_related("vendedor")
    for candidato in candidatos:
        if re.sub(r"\D", "", candidato.whatsapp or "") == numeros:
            return candidato
    return None


def _listar_vendedores_disponiveis(agora_local=None, lock=False):
    """Retorna lista de objetos VendedorRodizio elegiveis no rodizio."""
    hoje = timezone.localdate()
    agora_local = agora_local or timezone.localtime()
    hora_atual = agora_local.time()

    queryset = VendedorRodizio.objects.filter(ativo=True).select_related('vendedor', 'vendedor__dados_funcionais')
    if lock:
        # Serializa concorrentes na definicao do proximo vendedor (evita atribuir o mesmo vendedor duas vezes).
        # of=('self',) restringe o lock so a tabela de VendedorRodizio: sem isso o Postgres
        # rejeita com "FOR UPDATE cannot be applied to the nullable side of an outer join",
        # porque vendedor__dados_funcionais e o lado reverso de um OneToOneField (nem todo
        # User tem Funcionario), resolvido com LEFT OUTER JOIN.
        queryset = queryset.select_for_update(of=('self',))
    candidatos = list(queryset)
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
    with transaction.atomic():
        vendedores_elegiveis = _listar_vendedores_disponiveis(lock=True)
        proximo = vendedores_elegiveis[0] if vendedores_elegiveis else None

        if not proximo:
            return None

        # Atualiza o horario para o momento atual (fim da fila)
        proximo.ultima_atribuicao = timezone.now()
        proximo.save(update_fields=["ultima_atribuicao"])

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
        logger.warning("Falha no Webhook n8n para cliente %s: %s", cliente.pk, e)


def _normalizar_telefone_evo(telefone):
    numeros = re.sub(r"\D", "", telefone or "")
    if not numeros:
        return ""
    if numeros.startswith("55"):
        return f"+{numeros}"
    if len(numeros) in {10, 11}:
        return f"+55{numeros}"
    return f"+{numeros}"


def _montar_payload_evo_crm(cliente):
    telefone = _normalizar_telefone_evo(cliente.whatsapp)
    contato = {
        "name": cliente.nome_cliente,
        "email": cliente.email or "",
        "identifier": f"spagi-lead-{cliente.pk}",
    }
    if telefone:
        contato["phone_number"] = telefone

    deal = {
        "pipeline_id": settings.EVO_CRM_PIPELINE_ID,
    }
    if settings.EVO_CRM_PIPELINE_STAGE_ID:
        deal["stage_id"] = settings.EVO_CRM_PIPELINE_STAGE_ID

    return {
        "contact": contato,
        "deal": deal,
        "custom_fields": {
            "source": cliente.fonte_cliente or "distribuicao",
            "campaign": "spagi-distribuicao",
            "tipo_veiculo": cliente.tipo_veiculo or "",
            "marca_veiculo": cliente.marca_veiculo or "",
            "modelo_veiculo": cliente.modelo_veiculo or "",
            "ano_veiculo": cliente.ano_veiculo or "",
            "vendedor_atribuido": cliente.vendedor.username if cliente.vendedor else "",
        },
        "metadata": {
            "cliente_id": cliente.id,
            "tipo_veiculo": cliente.tipo_veiculo or "",
            "marca_veiculo": cliente.marca_veiculo or "",
            "modelo_veiculo": cliente.modelo_veiculo or "",
            "observacao": cliente.observacao or "",
        },
    }


def _extrair_ids_evo_crm(data):
    retorno = data.get("data") or {}

    lead_id = retorno.get("lead_id")
    deal_id = retorno.get("deal_id")

    if lead_id or deal_id:
        return lead_id, deal_id, retorno

    lead = retorno.get("lead") or retorno.get("contact") or {}
    deal = retorno.get("deal") or retorno.get("pipeline_item") or {}

    lead_id = (
        lead.get("id")
        or lead.get("lead_id")
        or retorno.get("id")
    )
    deal_id = (
        deal.get("id")
        or deal.get("deal_id")
        or retorno.get("deal", {}).get("id")
    )

    return lead_id, deal_id, retorno


def _resposta_indica_jornada_ativa(corpo_resposta):
    texto = (corpo_resposta or "").lower()
    return "active journey" in texto and "pipeline" in texto


def criar_lead_evo_crm(cliente):
    """Cria o lead no Evo CRM sem interromper o fluxo local de distribuicao."""
    if cliente.evo_crm_lead_id and cliente.evo_crm_deal_id:
        return {"success": True, "skipped": True, "reason": "already_synced", "configured": True}

    if not settings.EVO_CRM_API_TOKEN or not settings.EVO_CRM_PIPELINE_ID:
        return {"success": False, "skipped": True, "reason": "not_configured", "configured": False}

    base_url = (settings.EVO_CRM_API_URL or "https://api.evoai.app").rstrip("/")
    endpoint = f"{base_url}/public/api/v1/leads"
    payload = _montar_payload_evo_crm(cliente)
    headers = {
        "Content-Type": "application/json",
        "api_access_token": settings.EVO_CRM_API_TOKEN,
    }

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=settings.EVO_CRM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            raise ValueError(data.get("message") or "Evo CRM retornou sucesso=False.")

        lead_id, deal_id, retorno = _extrair_ids_evo_crm(data)

        if not lead_id or not deal_id:
            cliente.evo_crm_pipeline_id = settings.EVO_CRM_PIPELINE_ID
            cliente.save(update_fields=["evo_crm_pipeline_id", "data_ultimo_contato"])
            logger.info(
                "Lead do cliente %s criado no Evo CRM sem IDs de retorno. resposta=%s payload=%s",
                cliente.pk,
                data,
                payload,
            )
            return {
                "success": True,
                "skipped": True,
                "configured": True,
                "reason": "created_without_ids",
                "raw_response": data,
            }

        cliente.evo_crm_lead_id = lead_id
        cliente.evo_crm_deal_id = deal_id
        cliente.evo_crm_pipeline_id = settings.EVO_CRM_PIPELINE_ID
        cliente.save(update_fields=["evo_crm_lead_id", "evo_crm_deal_id", "evo_crm_pipeline_id", "data_ultimo_contato"])

        return {
            "success": True,
            "skipped": False,
            "configured": True,
            "lead_id": lead_id,
            "deal_id": deal_id,
        }
    except requests.HTTPError as exc:
        corpo_resposta = ""
        try:
            corpo_resposta = exc.response.text
        except Exception:
            corpo_resposta = ""

        if getattr(exc.response, "status_code", None) == 422 and _resposta_indica_jornada_ativa(corpo_resposta):
            cliente.evo_crm_pipeline_id = settings.EVO_CRM_PIPELINE_ID
            cliente.save(update_fields=["evo_crm_pipeline_id", "data_ultimo_contato"])
            logger.info(
                "Contato do cliente %s ja possui jornada ativa no pipeline do Evo CRM. body=%s",
                cliente.pk,
                corpo_resposta,
            )
            return {
                "success": True,
                "skipped": True,
                "configured": True,
                "reason": "active_journey_exists",
                "response_body": corpo_resposta,
            }

        logger.warning(
            "Falha ao criar lead no Evo CRM para cliente %s: status=%s body=%s payload=%s",
            cliente.pk,
            getattr(exc.response, "status_code", "n/a"),
            corpo_resposta,
            payload,
        )
        return {
            "success": False,
            "skipped": False,
            "configured": True,
            "error": str(exc),
            "response_body": corpo_resposta,
        }
    except Exception as exc:
        logger.warning("Falha ao criar lead no Evo CRM para cliente %s: %s | payload=%s", cliente.pk, exc, payload)
        return {
            "success": False,
            "skipped": False,
            "configured": True,
            "error": str(exc),
        }
