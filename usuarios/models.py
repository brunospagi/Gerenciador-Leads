from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    class NivelAcesso(models.TextChoices):
        VENDEDOR = 'VENDEDOR', 'Vendedor'
        GERENTE = 'GERENTE', 'Gerente'
        ADMIN = 'ADMIN', 'Administrador'

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nivel_acesso = models.CharField(
        max_length=10,
        choices=NivelAcesso.choices,
        default=NivelAcesso.VENDEDOR
    )

    def __str__(self):
        return f'{self.user.username} Profile'

# Esta função cria um perfil automaticamente sempre que um novo usuário é criado.
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()