from .models import Notificacao

def unread_notifications_context(request):
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        unread_count = Notificacao.objects.filter(usuario=user, lida=False).count()
        return {'unread_notifications_count': unread_count}
    return {}
