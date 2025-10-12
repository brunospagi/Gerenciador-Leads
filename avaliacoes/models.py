from django.db import models
from django.utils import timezone
from datetime import timedelta

class Avaliacao(models.Model):
    STATUS_CHOICES = (
        ('disponivel', 'Disponível'),
        ('finalizado', 'Finalizado'),
    )

    placa = models.CharField(max_length=10, unique=True)
    modelo = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20)
    valor_pretendido = models.DecimalField(max_digits=10, decimal_places=2)
    observacao = models.TextField(blank=True, null=True)
    valor_avaliado = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='disponivel')

    def __str__(self):
        return f"{self.modelo} - {self.placa}"

    @property
    def is_expired(self):
        return timezone.now() > self.data_criacao + timedelta(days=30)

    def save(self, *args, **kwargs):
        if self.is_expired:
            self.status = 'finalizado'
        super().save(*args, **kwargs)

def get_upload_path(instance, filename):
    return f'avaliacoes/{instance.avaliacao.placa}/{filename}'

class AvaliacaoFoto(models.Model):
    avaliacao = models.ForeignKey(Avaliacao, related_name='fotos', on_delete=models.CASCADE)
    foto = models.ImageField(upload_to=get_upload_path)

    def __str__(self):
        return f"Foto de {self.avaliacao.modelo}"