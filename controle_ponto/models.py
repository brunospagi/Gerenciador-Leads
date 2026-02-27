from django.db import models
from funcionarios.models import Funcionario

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
        verbose_name = "Registo de Ponto"
        verbose_name_plural = "Registos de Ponto"
        unique_together = ('funcionario', 'data')

    def __str__(self):
        return f"Ponto: {self.funcionario.user.get_full_name()} - {self.data.strftime('%d/%m/%Y')}"