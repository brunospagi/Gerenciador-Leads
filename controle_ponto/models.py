from django.db import models
from django.contrib.auth.models import User
from funcionarios.models import Funcionario


class ConfiguracaoPonto(models.Model):
    """Tabela de configuração única para as regras do Ponto Eletrônico."""
    ip_permitido = models.CharField(
        max_length=50,
        default='*',
        verbose_name="IP Permitido da Loja",
        help_text="Coloque o IP fixo da loja ou deixe '*' para aceitar qualquer IP.",
    )
    latitude_loja = models.CharField(max_length=50, default='-25.4284', verbose_name="Latitude da Loja (Central)")
    longitude_loja = models.CharField(max_length=50, default='-49.2733', verbose_name="Longitude da Loja (Central)")
    raio_permitido = models.IntegerField(
        default=100,
        verbose_name="Raio Permitido (em metros)",
        help_text="Distância máxima que o funcionário pode estar da loja para bater o ponto.",
    )
    horario_escala_entrada = models.TimeField(default='08:00', verbose_name="Horário Escala de Entrada")
    tolerancia_atraso_minutos = models.PositiveIntegerField(default=5, verbose_name="Tolerância de Atraso (min)")

    class Meta:
        verbose_name = "Configuração do Ponto"
        verbose_name_plural = "Configurações do Ponto"

    def save(self, *args, **kwargs):
        # Garante que só existe 1 linha nesta tabela (ID = 1)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Regras de Segurança de Ponto"


class RegistroPonto(models.Model):
    class StatusHomologacao(models.TextChoices):
        NAO_APLICA = 'NAO_APLICA', 'Não se aplica'
        PENDENTE = 'PENDENTE', 'Pendente de Homologação'
        ACEITO = 'ACEITO', 'Aceito'
        RECUSADO = 'RECUSADO', 'Recusado'

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='pontos')
    data = models.DateField(auto_now_add=True, verbose_name="Data do Ponto")

    entrada = models.TimeField(null=True, blank=True, verbose_name="Entrada")
    foto_entrada = models.TextField(null=True, blank=True, verbose_name="Foto Entrada (Base64)")

    saida_almoco = models.TimeField(null=True, blank=True, verbose_name="Saída Almoço")
    foto_saida_almoco = models.TextField(null=True, blank=True, verbose_name="Foto Saída Almoço")

    retorno_almoco = models.TimeField(null=True, blank=True, verbose_name="Retorno Almoço")
    foto_retorno_almoco = models.TextField(null=True, blank=True, verbose_name="Foto Retorno Almoço")

    saida = models.TimeField(null=True, blank=True, verbose_name="Saída")
    foto_saida = models.TextField(null=True, blank=True, verbose_name="Foto Saída")

    # Dados de segurança e localização
    ip_registrado = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP da Máquina")
    latitude = models.CharField(max_length=50, null=True, blank=True, verbose_name="Latitude")
    longitude = models.CharField(max_length=50, null=True, blank=True, verbose_name="Longitude")

    # Regras e ocorrências de entrada
    horario_escala_entrada = models.TimeField(null=True, blank=True, verbose_name="Escala de Entrada (dia)")
    tolerancia_entrada_minutos = models.PositiveIntegerField(default=5, verbose_name="Tolerância aplicada (min)")
    atraso_minutos = models.PositiveIntegerField(default=0, verbose_name="Atraso na Entrada (min)")
    justificativa_atraso = models.TextField(blank=True, null=True, verbose_name="Justificativa do Atraso")
    status_homologacao = models.CharField(
        max_length=12,
        choices=StatusHomologacao.choices,
        default=StatusHomologacao.NAO_APLICA,
        verbose_name="Status da Homologação",
    )
    homologado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='homologacoes_ponto',
        verbose_name="Homologado por",
    )
    homologado_em = models.DateTimeField(null=True, blank=True, verbose_name="Data da Homologação")
    observacao_homologacao = models.TextField(blank=True, null=True, verbose_name="Observação da Homologação")

    class Meta:
        verbose_name = "Registro de Ponto"
        verbose_name_plural = "Registros de Ponto"
        unique_together = ('funcionario', 'data')

    def __str__(self):
        return f"Ponto: {self.funcionario.nome_completo} - {self.data.strftime('%d/%m/%Y')}"
