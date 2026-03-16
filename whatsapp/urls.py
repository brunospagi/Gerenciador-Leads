from django.urls import path

from .views import WhatsAppInboxView, WhatsAppWebhookView, mark_read

app_name = 'whatsapp'

urlpatterns = [
    path('', WhatsAppInboxView.as_view(), name='inbox'),
    path('conversa/<int:pk>/marcar-lida/', mark_read, name='mark_read'),
    path('webhook/', WhatsAppWebhookView.as_view(), name='webhook'),
]
