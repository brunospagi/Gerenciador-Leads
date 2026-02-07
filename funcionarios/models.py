from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

class Funcionario(models.Model):
    TIPO_CONTA_CHOICES = [
        ('CORRENTE', 'Conta Corrente'),
        ('POUPANCA', 'Poupança'),
        ('SALARIO', 'Conta Salário'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dados_funcionais', verbose_name="Usuário do Sistema")
    
    # Dados Pessoais
    cpf = models.CharField(max_length=14, unique=True, verbose_name="CPF")
    rg = models.CharField(max_length=20, blank=True, null=True, verbose_name="RG")
    data_nascimento = models.DateField(blank=True, null=True, verbose_name="Data de Nascimento")
    telefone = models.CharField(max_length=20, verbose_name="Telefone/WhatsApp")
    
    # Endereço
    endereco = models.CharField(max_length=255, verbose_name="Endereço Completo")
    cep = models.CharField(max_length=9, blank=True, null=True, verbose_name="CEP")

    # Dados Contratuais
    cargo = models.CharField(max_length=100, verbose_name="Cargo")
    data_admissao = models.DateField(verbose_name="Data de Admissão")
    salario_base = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Salário Base (R$)", validators=[MinValueValidator(0)])
    ativo = models.BooleanField(default=True, verbose_name="Colaborador Ativo?")

    # Dados Bancários
    banco = models.CharField(max_length=100, verbose_name="Nome do Banco")
    agencia = models.CharField(max_length=20, verbose_name="Agência")
    conta = models.CharField(max_length=30, verbose_name="Nº da Conta")
    tipo_conta = models.CharField(max_length=20, choices=TIPO_CONTA_CHOICES, default='CORRENTE', verbose_name="Tipo de Conta")
    chave_pix = models.CharField(max_length=100, blank=True, null=True, verbose_name="Chave Pix")

    # === CORREÇÃO DE EXIBIÇÃO ===
    @property
    def nome_completo(self):
        """Retorna Nome Completo. Se vazio, retorna o Username (Login)."""
        full_name = self.user.get_full_name()
        if full_name:
            return full_name
        return self.user.username

    def __str__(self):
        # Garante a exibição correta nos Dropdowns (Selects)
        return f"{self.nome_completo} - {self.cargo}"

    class Meta:
        verbose_name = "Cadastro Funcional"
        verbose_name_plural = "Cadastros Funcionais"