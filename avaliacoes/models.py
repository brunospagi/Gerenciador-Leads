# brunospagi/gerenciador-leads/Gerenciador-Leads-fecd02772f93afa4ca06347c8334383a86eb8295/avaliacoes/models.py

from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.utils.timezone import is_aware, make_aware
import uuid
import os
from crmspagi.storage_backends import PublicMediaStorage

def get_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{ext}"
    return f"avaliacoes/{instance.avaliacao.placa}/{unique_filename}"

class Avaliacao(models.Model):
    STATUS_CHOICES = (
        ('disponivel', 'Disponível'),
        ('finalizado', 'Finalizado'),
    )
    # --- Novos Campos ---
    marca = models.CharField(max_length=100, default='')
    modelo = models.CharField(max_length=100)
    ano = models.CharField(max_length=20, default='')
    # --- Fim dos Novos Campos ---
    
    placa = models.CharField(max_length=10, unique=True)
    telefone = models.CharField(max_length=20)
    valor_pretendido = models.DecimalField(max_digits=10, decimal_places=2)
    observacao = models.TextField(blank=True, null=True)
    valor_avaliado = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='disponivel')

    def __str__(self):
        return f"{self.marca} {self.modelo} {self.ano} - {self.placa}"

    @property
    def is_expired(self):
        if not self.data_criacao:
            return False
        now = timezone.now()
        data_criacao_aware = self.data_criacao
        if not is_aware(data_criacao_aware):
            data_criacao_aware = make_aware(data_criacao_aware, timezone.get_current_timezone())
        return now > data_criacao_aware + timedelta(days=30)

    def save(self, *args, **kwargs):
        if self.pk and self.is_expired:
            self.status = 'finalizado'
        super().save(*args, **kwargs)


class AvaliacaoFoto(models.Model):
    avaliacao = models.ForeignKey(Avaliacao, related_name='fotos', on_delete=models.CASCADE)
    foto = models.ImageField(
        upload_to=get_upload_path,
        storage=PublicMediaStorage()
    )

    def __str__(self):
        return f"Foto de {self.avaliacao.modelo}"