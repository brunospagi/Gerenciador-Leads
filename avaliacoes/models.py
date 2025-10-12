from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.utils.timezone import is_aware, make_aware

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
        """
        Verifica se a avaliação expirou (mais de 30 dias).
        Garante que a comparação de datetimes é segura em relação a timezones.
        """
        if not self.data_criacao:
            return False

        # Pega a data/hora atual ciente do fuso horário
        now = timezone.now()
        
        # Garante que a data_criacao também é ciente do fuso horário
        data_criacao_aware = self.data_criacao
        if not is_aware(data_criacao_aware):
            # Se por algum motivo a data no banco for ingênua, torna ela ciente
            data_criacao_aware = make_aware(data_criacao_aware, timezone.get_current_timezone())

        return now > data_criacao_aware + timedelta(days=30)

    def save(self, *args, **kwargs):
        # A lógica de expiração só deve ser aplicada em objetos que já existem (têm pk)
        if self.pk and self.is_expired:
            self.status = 'finalizado'
        
        # A chamada super().save() deve vir depois da lógica
        super().save(*args, **kwargs)

def get_upload_path(instance, filename):
    return f'avaliacoes/{instance.avaliacao.placa}/{filename}'

class AvaliacaoFoto(models.Model):
    avaliacao = models.ForeignKey(Avaliacao, related_name='fotos', on_delete=models.CASCADE)
    foto = models.ImageField(upload_to=get_upload_path)

    def __str__(self):
        return f"Foto de {self.avaliacao.modelo}"