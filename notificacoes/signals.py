from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from clientes.models import Cliente
from .models import Notificacao
# Importe o Profile para verificar o nível de acesso
from usuarios.models import Profile

@receiver(post_save, sender=Cliente)
def criar_notificacao_novo_lead(sender, instance, created, **kwargs):
    """
    Cria uma notificação para todos os administradores quando um novo lead (Cliente) é criado.
    """
    if created:
        # Encontra todos os usuários que são administradores
        admins = User.objects.filter(profile__nivel_acesso=Profile.NivelAcesso.ADMIN)
        mensagem = f"Novo lead cadastrado: {instance.nome_cliente}."
        
        for admin in admins:
            Notificacao.objects.create(usuario=admin, mensagem=mensagem)
            # Aqui você adicionaria a lógica para disparar e-mails e webhooks
            # Exemplo: send_email_notification.delay(admin.id, mensagem)
            # Exemplo: send_webhook_notification.delay(admin.id, mensagem)