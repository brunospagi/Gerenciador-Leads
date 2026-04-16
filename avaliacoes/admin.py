from django.contrib import admin

from .models import Avaliacao, AvaliacaoFoto, ConfiguracaoIA


class AvaliacaoFotoInline(admin.TabularInline):
    model = AvaliacaoFoto
    extra = 0


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('placa', 'marca', 'modelo', 'ano', 'status', 'data_criacao', 'cadastrado_por')
    search_fields = ('placa', 'marca', 'modelo', 'ano', 'telefone')
    list_filter = ('status', 'tipo_veiculo', 'data_criacao')
    inlines = [AvaliacaoFotoInline]


@admin.register(ConfiguracaoIA)
class ConfiguracaoIAAdmin(admin.ModelAdmin):
    list_display = ('provider', 'modelo', 'ativo', 'api_key_masked', 'atualizado_em')
    readonly_fields = ('provider', 'atualizado_em')
    fieldsets = (
        ('Configuração Gemini', {
            'fields': ('provider', 'ativo', 'modelo', 'api_key', 'atualizado_em'),
        }),
    )

    def has_add_permission(self, request):
        if ConfiguracaoIA.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='API Key')
    def api_key_masked(self, obj):
        if not obj.api_key:
            return '(usando .env)'
        tail = obj.api_key[-4:] if len(obj.api_key) >= 4 else obj.api_key
        return f'****{tail}'
