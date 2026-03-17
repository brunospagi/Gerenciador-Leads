from django.urls import path

from .views import (
    WhatsAppInboxView,
    WhatsAppInstanceConfigView,
    WhatsAppWebhookView,
    delete_conversation,
    conversation_messages_feed,
    conversations_feed,
    forward_message,
    forward_messages_bulk,
    instance_runtime_status,
    mark_read,
    react_message,
)

app_name = 'whatsapp'

urlpatterns = [
    path('', WhatsAppInboxView.as_view(), name='inbox'),
    path('feed/conversas/', conversations_feed, name='conversations_feed'),
    path('feed/conversa/<int:pk>/mensagens/', conversation_messages_feed, name='conversation_messages_feed'),
    path('mensagem/<int:pk>/reagir/', react_message, name='react_message'),
    path('mensagem/<int:pk>/encaminhar/', forward_message, name='forward_message'),
    path('mensagem/encaminhar/lote/', forward_messages_bulk, name='forward_messages_bulk'),
    path('instancia/', WhatsAppInstanceConfigView.as_view(), name='instance_config'),
    path('instancia/<int:pk>/status/', instance_runtime_status, name='instance_runtime_status'),
    path('conversa/<int:pk>/marcar-lida/', mark_read, name='mark_read'),
    path('conversa/<int:pk>/deletar/', delete_conversation, name='delete_conversation'),
    path('webhook', WhatsAppWebhookView.as_view(), name='webhook_no_slash'),
    path('webhook/', WhatsAppWebhookView.as_view(), name='webhook'),
    path('webhook/<slug:event_name>', WhatsAppWebhookView.as_view(), name='webhook_event_no_slash'),
    path('webhook/<slug:event_name>/', WhatsAppWebhookView.as_view(), name='webhook_event'),
]
