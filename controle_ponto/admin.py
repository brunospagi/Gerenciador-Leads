from django.contrib import admin
from .models import RegistroPonto, ConfiguracaoPonto

@admin.register(ConfiguracaoPonto)
class ConfiguracaoPontoAdmin(admin.ModelAdmin):
    list_display = (
        '__str__',
        'ip_permitido',
        'raio_permitido',
        'horario_escala_entrada',
        'tolerancia_atraso_minutos',
        'facetec_habilitado',
        'latitude_loja',
        'longitude_loja',
    )
    
    # Remove o botão de "Adicionar" se já existir a configuração (para evitar duplicações)
    def has_add_permission(self, request):
        if ConfiguracaoPonto.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    fieldsets = (
        ('Segurança de Rede/Localização', {
            'fields': (
                'ip_permitido',
                ('latitude_loja', 'longitude_loja'),
                'raio_permitido',
            )
        }),
        ('Escala e Regras de Atraso', {
            'fields': (
                'horario_escala_entrada',
                'tolerancia_atraso_minutos',
            )
        }),
        ('FaceTec SDK', {
            'fields': (
                'facetec_habilitado',
                'facetec_modo_producao',
                'facetec_base_url',
                'facetec_device_key_identifier',
                'facetec_public_face_scan_encryption_key',
                'facetec_production_key',
            )
        }),
    )

@admin.register(RegistroPonto)
class RegistroPontoAdmin(admin.ModelAdmin):
    list_display = (
        'funcionario',
        'data',
        'entrada',
        'horario_escala_entrada',
        'atraso_minutos',
        'status_homologacao',
        'homologado_por',
        'ip_registrado',
    )
    list_filter = ('data', 'funcionario', 'status_homologacao')
    search_fields = ('funcionario__user__first_name', 'funcionario__user__last_name', 'ip_registrado', 'justificativa_atraso')
    autocomplete_fields = ('funcionario', 'homologado_por')
    date_hierarchy = 'data'
