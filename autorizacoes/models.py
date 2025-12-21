from django.db import models
from django.contrib.auth import get_user_model
from clientes.models import Cliente # Opcional: para vincular a um cliente existente

User = get_user_model()

class Autorizacao(models.Model):
    TIPO_CHOICES = [
        ('TANQUE', 'Tanque Cheio'),
        ('TRANSFERENCIA', 'Transferência Grátis'),
        ('REPARO', 'Reparo / Manutenção'),
        ('ACESSORIO', 'Acessório (Insulfilm, Som, etc)'),
        ('DOCUMENTACAO', 'Documentação / IPVA'),
        ('OUTRO', 'Outros'),
    ]

    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente de Aprovação'),
        ('APROVADO', 'Aprovado'),
        ('REJEITADO', 'Rejeitado'),
    ]

    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='autorizacoes_solicitadas')
    gerente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='autorizacoes_gerenciadas')
    
    # Dados do Veículo
    placa = models.CharField(max_length=10)
    modelo = models.CharField(max_length=100)
    ano = models.CharField(max_length=20)
    cor = models.CharField(max_length=30)
    
    # Detalhes da Autorização
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.TextField(verbose_name="Descrição Detalhada", help_text="Ex: Troca de pastilhas de freio ou Tanque cheio na entrega.")
    valor_estimado = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDENTE')
    
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    data_aprovacao = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.placa} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Autorização"
        verbose_name_plural = "Autorizações"
        ordering = ['-data_solicitacao']