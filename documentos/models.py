from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Outorgado(models.Model):
    """
    Armazena os dados dos outorgados (a lista de pessoas da empresa)
    que podem ser listados na procuração.
    """
    nome = models.CharField(max_length=255, verbose_name="Nome Completo")
    cpf = models.CharField(max_length=20, verbose_name="CPF", unique=True)

    class Meta:
        verbose_name = "Outorgado"
        verbose_name_plural = "Outorgados"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Procuracao(models.Model):
    """
    Armazena os dados variáveis de uma procuração,
    baseado no documento PROCURAÇÃO_XRE190.pdf.
    """
    class TipoDocumento(models.TextChoices):
        CPF = 'CPF', 'CPF'
        CNPJ = 'CNPJ', 'CNPJ'

    vendedor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='procuracoes_geradas')
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    # Dados do Outorgante (Quem está passando a procuração - Ex: JOAO EDGAR FREIRE)
    outorgante_nome = models.CharField(max_length=255, verbose_name="Nome do Outorgante (Vendedor do Veículo)")
    tipo_documento = models.CharField(max_length=4, choices=TipoDocumento.choices, default=TipoDocumento.CPF, verbose_name="Tipo de Documento")
    outorgante_documento = models.CharField(max_length=20, verbose_name="CPF/CNPJ do Outorgante")
    
    # Dados do Veículo
    veiculo_marca_modelo = models.CharField(max_length=100, verbose_name="Marca/Modelo")
    veiculo_ano_fab = models.CharField(max_length=4, verbose_name="Ano Fabricação")
    veiculo_ano_mod = models.CharField(max_length=4, verbose_name="Ano Modelo")
    veiculo_placa = models.CharField(max_length=10, verbose_name="Placa")
    veiculo_cor = models.CharField(max_length=50, verbose_name="Cor Predominante")
    veiculo_renavam = models.CharField(max_length=20, verbose_name="RENAVAM")

    class Meta:
        verbose_name = "Procuração"
        verbose_name_plural = "Procurações"
        ordering = ['-data_criacao']

    def __str__(self):
        return f"Procuração para {self.outorgante_nome} - Placa {self.veiculo_placa}"