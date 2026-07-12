from django.contrib import admin
from django.utils.html import format_html

from .models import EnvioWebhook, LoteGeracao, PostPromocional, VeiculoAnuncio


@admin.register(VeiculoAnuncio)
class VeiculoAnuncioAdmin(admin.ModelAdmin):
    list_display = (
        'titulo', 'tipo', 'marca', 'preco', 'ano', 'ipva_pago', 'aceita_troca', 'veiculo_completo',
        'ativo', 'atualizado_em',
    )
    list_filter = ('tipo', 'ativo', 'marca', 'ipva_pago', 'aceita_troca', 'veiculo_completo')
    search_fields = ('titulo', 'marca', 'modelo', 'external_id')
    readonly_fields = ('external_id', 'coletado_em', 'atualizado_em')
    ordering = ('-atualizado_em',)


@admin.register(LoteGeracao)
class LoteGeracaoAdmin(admin.ModelAdmin):
    list_display = ('pk', 'status', 'total_alvo', 'total_gerado', 'total_falhas', 'iniciado_por', 'criado_em')
    list_filter = ('status',)
    readonly_fields = ('alvo_ids', 'criado_em', 'concluido_em')


@admin.register(PostPromocional)
class PostPromocionalAdmin(admin.ModelAdmin):
    list_display = ('anuncio', 'status', 'preview', 'lote', 'gerado_por', 'gerado_em')
    list_filter = ('status', 'lote')
    search_fields = ('anuncio__titulo', 'legenda')
    readonly_fields = ('preview_grande', 'prompt_imagem', 'modelo_ia_imagem', 'modelo_ia_texto', 'gerado_em')
    autocomplete_fields = ('anuncio',)

    def preview(self, obj):
        if not obj.imagem:
            return '-'
        return format_html('<img src="{}" style="height:60px;border-radius:4px;" />', obj.imagem.url)
    preview.short_description = 'Prévia'

    def preview_grande(self, obj):
        if not obj.imagem:
            return '-'
        return format_html('<img src="{}" style="max-height:400px;border-radius:8px;" />', obj.imagem.url)
    preview_grande.short_description = 'Prévia'


@admin.register(EnvioWebhook)
class EnvioWebhookAdmin(admin.ModelAdmin):
    list_display = ('post', 'webhook', 'sucesso', 'status_code', 'enviado_por', 'enviado_em')
    list_filter = ('sucesso', 'webhook')
    readonly_fields = ('post', 'webhook', 'enviado_por', 'sucesso', 'status_code', 'erro', 'enviado_em')
