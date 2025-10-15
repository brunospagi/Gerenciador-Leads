from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import UserLoginActivity

def get_client_ip(request):
    """Obtém o endereço IP do cliente a partir do request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Cria um registro de UserLoginActivity toda vez que um usuário faz login.
    """
    UserLoginActivity.objects.create(
        user=user,
        ip_address=get_client_ip(request)
    )