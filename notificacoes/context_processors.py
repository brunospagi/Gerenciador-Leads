from .models import Notificacao

def unread_notifications_context(request):
    if request.user.is_authenticated:
        unread_count = Notificacao.objects.filter(usuario=request.user, lida=False).count()
        return {'unread_notifications_count': unread_count}
    return {}