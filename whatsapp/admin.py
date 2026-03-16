from django.contrib import admin

from .models import WhatsAppConversation, WhatsAppInstance, WhatsAppMessage


@admin.register(WhatsAppInstance)
class WhatsAppInstanceAdmin(admin.ModelAdmin):
    list_display = ('nome', 'instance_name', 'ativo', 'status_conexao', 'atualizado_em')
    search_fields = ('nome', 'instance_name')
    list_filter = ('ativo',)
    readonly_fields = ('qr_code_base64', 'ultima_resposta', 'atualizado_em')


@admin.register(WhatsAppConversation)
class WhatsAppConversationAdmin(admin.ModelAdmin):
    list_display = ('nome_exibicao', 'wa_id', 'nao_lidas', 'ultima_mensagem_em')
    search_fields = ('nome_contato', 'wa_id')
    list_filter = ('e_grupo',)


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ('conversa', 'direcao', 'status', 'criado_em')
    search_fields = ('external_id', 'conteudo', 'conversa__nome_contato', 'conversa__wa_id')
    list_filter = ('direcao', 'status')
