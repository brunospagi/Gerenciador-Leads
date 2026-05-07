from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Funcionario


def _cpf_temporario_por_user(user_id):
    # CPF técnico de 11 dígitos para não estourar max_length e manter unicidade por usuário.
    return f"{int(user_id):011d}"


@receiver(post_save, sender=User)
def criar_perfil_funcionario(sender, instance, created, **kwargs):
    if not created:
        return

    # Cadastro manual do RH cria Funcionario completo no fluxo da view.
    if getattr(instance, '_skip_funcionario_signal', False):
        return

    if hasattr(instance, 'dados_funcionais'):
        return

    Funcionario.objects.create(
        user=instance,
        cpf=_cpf_temporario_por_user(instance.id),
        telefone='A preencher',
        endereco='A preencher',
        cargo='Novo Colaborador',
        data_admissao=timezone.now().date(),
        salario_base=0.00,
        banco='A definir',
        agencia='0000',
        conta='00000-0',
    )


@receiver(post_save, sender=User)
def salvar_perfil_funcionario(sender, instance, **kwargs):
    # Garante que, se o User for salvo, o Funcionario também é atualizado se existir.
    if hasattr(instance, 'dados_funcionais'):
        instance.dados_funcionais.save()
