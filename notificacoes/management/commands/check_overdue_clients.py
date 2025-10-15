from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from notificacoes.models import Notificacao
from clientes.models import Cliente
from usuarios.models import Profile

class Command(BaseCommand):
    help = 'Verifica clientes com contato atrasado e notifica vendedores e administradores.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando verificação de clientes com contato atrasado...')

        # Encontra clientes com contato atrasado que não estão finalizados
        clientes_atrasados = Cliente.objects.filter(
            data_proximo_contato__lte=timezone.now()
        ).exclude(status_negociacao=Cliente.StatusNegociacao.FINALIZADO)

        if not clientes_atrasados.exists():
            self.stdout.write(self.style.SUCCESS('Nenhum cliente com contato atrasado encontrado.'))
            return

        # Busca todos os administradores
        admins = User.objects.filter(profile__nivel_acesso=Profile.NivelAcesso.ADMIN)

        for cliente in clientes_atrasados:
            vendedor = cliente.vendedor
            mensagem = f"Contato Atrasado: O cliente '{cliente.nome_cliente}' precisa de atenção. Próximo contato era em {cliente.data_proximo_contato.strftime('%d/%m/%Y')}."

            # 1. Notifica o vendedor responsável pelo cliente
            if vendedor:
                Notificacao.objects.get_or_create(
                    usuario=vendedor,
                    mensagem=mensagem,
                    defaults={'lida': False}
                )
                self.stdout.write(f"Notificação criada para o vendedor '{vendedor.username}' sobre o cliente '{cliente.nome_cliente}'.")

            # 2. Notifica todos os administradores
            for admin in admins:
                # Evita duplicidade se o vendedor já for um admin
                if not vendedor or vendedor.id != admin.id:
                    Notificacao.objects.get_or_create(
                        usuario=admin,
                        mensagem=f"Alerta geral: {mensagem}", # Mensagem pode ser diferenciada para o admin
                        defaults={'lida': False}
                    )
                    self.stdout.write(f"Notificação criada para o admin '{admin.username}' sobre o cliente '{cliente.nome_cliente}'.")

        self.stdout.write(self.style.SUCCESS('Verificação de contatos atrasados concluída.'))