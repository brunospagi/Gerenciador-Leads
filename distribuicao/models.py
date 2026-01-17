from django.db import models
from django.contrib.auth.models import User

class VendedorRodizio(models.Model):
    vendedor = models.OneToOneField(User, on_delete=models.CASCADE, related_name='config_rodizio')
    ativo = models.BooleanField(default=True, verbose_name="Participa do Rodízio?")
    ultima_atribuicao = models.DateTimeField(null=True, blank=True, verbose_name="Última Atribuição")
    ordem = models.PositiveIntegerField(default=0, help_text="Menor número recebe primeiro em caso de empate")

    class Meta:
        # Ordenação padrão: quem nunca recebeu (NULL) primeiro, depois data mais antiga
        ordering = ['ultima_atribuicao', 'ordem']
        verbose_name = "Configuração de Rodízio"
        verbose_name_plural = "Configurações de Rodízio"

    def __str__(self):
        status = "Ativo" if self.ativo else "Inativo"
        return f"{self.vendedor.username} ({status})"