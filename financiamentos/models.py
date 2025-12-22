from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Ficha(models.Model):
    STATUS_CHOICES = [
        ('NOVA', 'Nova'),
        ('EM_ANALISE', 'Em Análise'),
        ('APROVADA', 'Aprovada'),
        ('EM_ASSINATURA', 'Em Assinatura'),
        ('RECUSADA', 'Recusada'),
        ('CANCELADA', 'Cancelada'),
        ('EM_PAGAMENTO', 'Em Pagamento'),
        ('PAGO', 'Pago'),
        ('FINALIZADO', 'Finalizado'),
    ]

    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fichas')
    
    # Dados do Veículo e Cliente
    cliente_nome = models.CharField("Cliente", max_length=150)
    veiculo = models.CharField("Veículo", max_length=100)
    ano = models.CharField("Ano", max_length=20)
    placa = models.CharField("Placa", max_length=10)
    valor_veiculo = models.DecimalField("Valor Veículo", max_digits=12, decimal_places=2)
    
    # Dados do Financiamento
    banco = models.CharField("Banco", max_length=50)
    qtd_parcelas = models.IntegerField("Qtd Parcelas")
    valor_parcela = models.DecimalField("Valor Parcela", max_digits=10, decimal_places=2)
    valor_financiado = models.DecimalField("Valor Financiado", max_digits=12, decimal_places=2, help_text="Valor líquido financiado")
    
    # Retorno (Comissão)
    porcentagem_retorno = models.DecimalField("% Retorno", max_digits=5, decimal_places=2, default=0)
    valor_retorno = models.DecimalField("Valor Retorno (R$)", max_digits=10, decimal_places=2, editable=False, default=0)
    
    # Controle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOVA')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ficha de Financiamento"
        verbose_name_plural = "Fichas de Financiamento"
        ordering = ['-data_atualizacao']

    def save(self, *args, **kwargs):
        # Calcula valor do retorno automaticamente: (Financiado * %) / 100
        if self.valor_financiado and self.porcentagem_retorno:
            self.valor_retorno = (self.valor_financiado * self.porcentagem_retorno) / 100
        else:
            self.valor_retorno = 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente_nome} - {self.veiculo}"