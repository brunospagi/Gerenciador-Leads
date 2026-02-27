from django.db import models
from funcionarios.models import Funcionario

class ConfiguracaoPonto(models.Model):
    """ Tabela de configuração única para as regras do Ponto Eletrônico """
    ip_permitido = models.CharField(max_length=50, default='*', verbose_name="IP Permitido da Loja", help_text="Coloque o IP Fixo da loja ou deixe '*' para aceitar qualquer IP.")
    latitude_loja = models.CharField(max_length=50, default='-25.4284', verbose_name="Latitude da Loja (Central)")
    longitude_loja = models.CharField(max_length=50, default='-49.2733', verbose_name="Longitude da Loja (Central)")
    raio_permitido = models.IntegerField(default=100, verbose_name="Raio Permitido (em metros)", help_text="Distância máxima que o funcionário pode estar da loja para bater o ponto.")

    class Meta:
        verbose_name = "Configuração do Ponto"
        verbose_name_plural = "Configurações do Ponto"

    def save(self, *args, **kwargs):
        # Garante que só existe 1 linha nesta tabela (ID = 1)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Regras de Segurança de Ponto"


class RegistroPonto(models.Model):
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
    
    # Dados de Segurança e Localização
    ip_registrado = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP da Máquina")
    latitude = models.CharField(max_length=50, null=True, blank=True, verbose_name="Latitude")
    longitude = models.CharField(max_length=50, null=True, blank=True, verbose_name="Longitude")

    class Meta:
        verbose_name = "Registro de Ponto"
        verbose_name_plural = "Registros de Ponto"
        unique_together = ('funcionario', 'data')

    def __str__(self):
        return f"Ponto: {self.funcionario.nome_completo} - {self.data.strftime('%d/%m/%Y')}"