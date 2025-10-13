from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from notificacoes.models import Notificacao
from usuarios.models import Profile

class Command(BaseCommand):
    help = 'Verifica usuários inativos há mais de 3 dias e notifica os administradores.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando verificação de usuários inativos...')

        # Define o período de inatividade (3 dias atrás a partir de agora)
        periodo_inatividade = timezone.now() - timedelta(days=3)

        # Encontra todos os usuários (não superusuários/staff) que não fazem login desde o período definido
        usuarios_inativos = User.objects.filter(
            last_login__lt=periodo_inatividade,
            is_superuser=False,
            is_staff=False
        )

        if not usuarios_inativos.exists():
            self.stdout.write(self.style.SUCCESS('Nenhum usuário inativo encontrado.'))
            return

        # Encontra todos os administradores do sistema
        admins = User.objects.filter(profile__nivel_acesso=Profile.NivelAcesso.ADMIN)

        if not admins.exists():
            self.stdout.write(self.style.WARNING('Nenhum administrador encontrado para notificar.'))
            return

        # Para cada usuário inativo, cria uma notificação para cada administrador
        for usuario in usuarios_inativos:
            mensagem = f"Alerta de Inatividade: O usuário '{usuario.username}' não acessa o sistema há mais de 3 dias."
            
            for admin in admins:
                # 'get_or_create' é usado para evitar criar notificações duplicadas.
                # Se uma notificação idêntica para o mesmo admin já existir, nada acontece.
                notificacao, criada = Notificacao.objects.get_or_create(
                    usuario=admin,
                    mensagem=mensagem,
                    defaults={'lida': False} # Só define 'lida=False' se estiver criando
                )
                if criada:
                    self.stdout.write(f"Notificação criada para '{admin.username}' sobre '{usuario.username}'.")

        self.stdout.write(self.style.SUCCESS('Verificação de inatividade concluída.'))