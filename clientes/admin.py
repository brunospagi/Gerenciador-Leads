from django.contrib import admin
from .models import Cliente, Historico, LeadAndamento


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        "nome_cliente",
        "whatsapp",
        "vendedor",
        "status_negociacao",
        "status_contato",
        "etapa_funil",
        "prioridade",
        "data_ultimo_contato",
        "data_proximo_contato",
    )
    list_filter = ("status_negociacao", "status_contato", "etapa_funil", "prioridade", "tipo_veiculo")
    search_fields = ("nome_cliente", "whatsapp", "marca_veiculo", "modelo_veiculo", "fonte_cliente")
    autocomplete_fields = ("vendedor",)
    date_hierarchy = "data_ultimo_contato"


@admin.register(Historico)
class HistoricoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "data_interacao")
    search_fields = ("cliente__nome_cliente", "motivacao")
    autocomplete_fields = ("cliente",)
    date_hierarchy = "data_interacao"


@admin.register(LeadAndamento)
class LeadAndamentoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "usuario", "status_contato", "etapa_funil", "data_proxima_acao", "criado_em")
    list_filter = ("status_contato", "etapa_funil", "criado_em")
    search_fields = ("cliente__nome_cliente", "comentario", "usuario__username")
    autocomplete_fields = ("cliente", "usuario")
    date_hierarchy = "criado_em"
