from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Funcionario
from django.utils import timezone

@receiver(post_save, sender=User)
def criar_perfil_funcionario(sender, instance, created, **kwargs):
    if created:
        # Cria um perfil funcional básico sempre que um User é criado
        Funcionario.objects.create(
            user=instance,
            cpf=f"00000000000-{instance.id}", # CPF Temporário para não quebrar unique
            telefone="A preencher",
            endereco="A preencher",
            cargo="Novo Colaborador",
            data_admissao=timezone.now().date(),
            salario_base=0.00,
            banco="A definir",
            agencia="0000",
            conta="00000-0"
        )

@receiver(post_save, sender=User)
def salvar_perfil_funcionario(sender, instance, **kwargs):
    # Garante que, se o User for salvo, o Funcionario também é atualizado se existir
    if hasattr(instance, 'dados_funcionais'):
        instance.dados_funcionais.save()