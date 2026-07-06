import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = (
        "Cria usuarios de teste (ADMIN, GERENTE, VENDEDOR) com cadastro funcional "
        "completo, para desenvolvimento local. Idempotente - seguro rodar de novo "
        "a qualquer momento. So funciona contra um banco SQLite (nunca roda em "
        "Postgres) para evitar criar contas de senha conhecida em ambiente real."
    )

    SENHA_PADRAO = "teste12345"

    USUARIOS = [
        {
            "username": "admin_teste",
            "first_name": "Admin",
            "nivel_acesso": "ADMIN",
            "is_superuser": True,
            "cargo": "Administrador",
            "cpf": "111.111.111-11",
        },
        {
            "username": "gerente_teste",
            "first_name": "Gerente",
            "nivel_acesso": "GERENTE",
            "is_superuser": False,
            "cargo": "Gerente de Loja",
            "cpf": "222.222.222-22",
        },
        {
            "username": "vendedor_teste",
            "first_name": "Vendedor",
            "nivel_acesso": "VENDEDOR",
            "is_superuser": False,
            "cargo": "Vendedor",
            "cpf": "333.333.333-33",
        },
    ]

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError(
                "Este comando so roda contra SQLite (evita criar usuarios com "
                "senha conhecida em bancos reais). Configure DB_ENGINE=sqlite "
                "no .env antes de rodar."
            )

        for dados in self.USUARIOS:
            user, _ = User.objects.get_or_create(
                username=dados["username"],
                defaults={"email": f"{dados['username']}@teste.local"},
            )
            user.first_name = dados["first_name"]
            user.last_name = "Teste"
            user.email = f"{dados['username']}@teste.local"
            user.is_superuser = dados["is_superuser"]
            user.is_staff = dados["is_superuser"]
            user.set_password(self.SENHA_PADRAO)
            user.save()

            profile = user.profile
            profile.nivel_acesso = dados["nivel_acesso"]
            profile.save()

            func = user.dados_funcionais
            func.cargo = dados["cargo"]
            func.cpf = dados["cpf"]
            func.rg = f"{user.pk:07d}-PR"
            func.data_nascimento = datetime.date(1990, 1, 1)
            func.telefone = "(41) 99999-0000"
            func.endereco = "Rua de Teste, 100"
            func.cep = "80000-000"
            func.data_admissao = datetime.date(2024, 1, 1)
            func.salario_base = 2500
            func.banco = "Banco de Teste"
            func.agencia = "0001"
            func.conta = "12345-6"
            func.save()

            self.stdout.write(self.style.SUCCESS(
                f"OK  {dados['username']:16} ({dados['nivel_acesso']:9}) senha={self.SENHA_PADRAO}"
            ))

        self.stdout.write(self.style.SUCCESS("\nUsuarios de teste prontos. Login em /contas/login/"))
