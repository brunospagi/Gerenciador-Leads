import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from clientes.models import Cliente
from usuarios.models import Profile
from .utils import notificar_usuario

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Cliente)
def criar_notificacao_novo_lead(sender, instance, created, **kwargs):
    """
    Cria uma notificação para todos os administradores quando um novo lead (Cliente) é criado.
    """
    if created:
        admins = User.objects.filter(profile__nivel_acesso=Profile.NivelAcesso.ADMIN)
        mensagem = f"Novo lead cadastrado: {instance.nome_cliente}."

        for admin in admins:
            notificar_usuario(admin, mensagem, url="/notificacoes/", titulo="Novo Lead Recebido!")