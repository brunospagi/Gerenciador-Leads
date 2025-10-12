from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.utils.timezone import is_aware, make_aware
import uuid
import os
# 1. IMPORTE A NOSSA CLASSE DE STORAGE PERSONALIZADA
from crmspagi.storage_backends import PublicMediaStorage

def get_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{ext}"
    return f"avaliacoes/{instance.avaliacao.placa}/{unique_filename}"

class Avaliacao(models.Model):
    # ... (o seu modelo Avaliacao, que já está correto, permanece aqui) ...
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
    
    # 2. AQUI ESTÁ A CORREÇÃO FINAL:
    # Forçamos este campo a usar a nossa classe PublicMediaStorage,
    # ignorando completamente a configuração DEFAULT_FILE_STORAGE.
    foto = models.ImageField(
        upload_to=get_upload_path,
        storage=PublicMediaStorage() # <-- FORÇA O UPLOAD PARA O MINIO
    )

    def __str__(self):
        return f"Foto de {self.avaliacao.modelo}"