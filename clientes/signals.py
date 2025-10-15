from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Cliente, Historico

# Usamos o 'pre_save' para ter acesso ao estado ANTES e DEPOIS da alteração
@receiver(pre_save, sender=Cliente)
def criar_historico_mudanca_status(sender, instance, **kwargs):
    """
    Cria um registro de histórico quando o status de negociação de um Cliente é alterado.
    """
    # Se o objeto é novo, não há o que comparar. Apenas sai da função.
    if instance._state.adding:
        return

    try:
        # Pega o estado do cliente como ele está no banco de dados AGORA (antes de salvar)
        original = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        # Se o objeto não existe ainda, não faz nada.
        return

    # Compara o status antigo com o novo status (que está na 'instance')
    if original.status_negociacao != instance.status_negociacao:
        # Se o NOVO status for "Agendado", cria um histórico detalhado
        if instance.status_negociacao == Cliente.StatusNegociacao.AGENDADO:
            data_formatada = instance.data_proximo_contato.strftime('%d/%m/%Y às %H:%M')
            motivacao = f"Visita agendada para {data_formatada} pelo vendedor {instance.vendedor.username}."
            Historico.objects.create(
                cliente=instance,
                motivacao=motivacao
            )
        else:  # Para qualquer outra mudança de status, cria a mensagem padrão
            Historico.objects.create(
                cliente=instance,
                motivacao=f"Status alterado de '{original.get_status_negociacao_display()}' para '{instance.get_status_negociacao_display()}'."
            )