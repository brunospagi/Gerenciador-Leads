# distribuicao/models.py
from django.db import models
from django.contrib.auth.models import User

class VendedorRodizio(models.Model):
    vendedor = models.OneToOneField(User, on_delete=models.CASCADE, related_name='config_rodizio')
    ativo = models.BooleanField(default=True, verbose_name="Participa do Rodízio?")
    ultima_atribuicao = models.DateTimeField(null=True, blank=True, verbose_name="Última Atribuição")
    
    # Campo opcional para definir uma ordem fixa (1, 2, 3...) se preferir não usar data/hora
    ordem = models.PositiveIntegerField(default=0, help_text="Menor número recebe primeiro")

    class Meta:
        ordering = ['ultima_atribuicao', 'ordem'] # Quem recebeu há mais tempo (None vem primeiro) é o próximo
        verbose_name = "Configuração de Rodízio"
        verbose_name_plural = "Configurações de Rodízio"

    def __str__(self):
        status = "Ativo" if self.ativo else "Inativo"
        return f"{self.vendedor.username} ({status})"