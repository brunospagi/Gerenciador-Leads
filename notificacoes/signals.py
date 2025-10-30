from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from clientes.models import Cliente
from .models import Notificacao
from usuarios.models import Profile
from webpush import send_user_notification # --- NOVO IMPORT ---
import json

@receiver(post_save, sender=Cliente)
def criar_notificacao_novo_lead(sender, instance, created, **kwargs):
    """
    Cria uma notificação para todos os administradores quando um novo lead (Cliente) é criado.
    """
    if created:
        admins = User.objects.filter(profile__nivel_acesso=Profile.NivelAcesso.ADMIN)
        mensagem = f"Novo lead cadastrado: {instance.nome_cliente}."
        
        for admin in admins:
            # 1. Cria a notificação no banco de dados
            Notificacao.objects.create(usuario=admin, mensagem=mensagem)
            
            # --- NOVO: 2. Tenta enviar uma Notificação Push ---
            try:
                # Prepara os dados do PUSH
                push_payload = {
                    "head": "Novo Lead Recebido!",
                    "body": mensagem,
                    "icon": "/static/images/logo-spagi-192x192.png",
                    "url": "/notificacoes/" # Para onde o usuário vai ao clicar
                }
                
                # Envia a notificação para todos os dispositivos logados desse admin
                send_user_notification(
                    user=admin,
                    payload=push_payload,
                    ttl=1000
                )
            except Exception as e:
                # Se o usuário não tiver um dispositivo PUSH,
                # a biblioteca `webpush` pode lançar uma exceção.
                # Apenas logamos e continuamos, pois a notificação
                # interna (no banco) já foi salva.
                print(f"Erro ao enviar Push Notification para {admin.username}: {e}")
            # --- FIM NOVO ---