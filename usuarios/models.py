from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from crmspagi.storage_backends import PublicMediaStorage # <-- IMPORTADO
from django.templatetags.static import static # <-- IMPORTADO

def get_avatar_upload_path(instance, filename):
    # Salva como avatars/user_<id>/<filename>
    # 'instance' é o objeto Profile
    return f"avatars/user_{instance.user.id}/{filename}"

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
    
    # --- NOVO CAMPO DE AVATAR ---
    avatar = models.ImageField(
        upload_to=get_avatar_upload_path,
        storage=PublicMediaStorage(), # Usa seu storage MinIO
        null=True,
        blank=True,
        verbose_name="Foto de Perfil"
    )

    def __str__(self):
        return f'{self.user.username} Profile'

    # --- NOVO MÉTODO PARA PEGAR A URL ---
    @property
    def get_avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        # Retorna o avatar padrão que estava no base.html
        return 'https://cdn.quasar.dev/img/boy-avatar.png'

# Esta função cria um perfil automaticamente sempre que um novo usuário é criado.
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class UserLoginActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_activities')
    login_timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-login_timestamp']

    def __str__(self):
        return f'{self.user.username} logou em {self.login_timestamp.strftime("%d/%m/%Y %H:%M")}'