from django.contrib import admin
from .models import RegistroPonto, ConfiguracaoPonto

@admin.register(ConfiguracaoPonto)
class ConfiguracaoPontoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'ip_permitido', 'raio_permitido', 'latitude_loja', 'longitude_loja')
    
    # Remove o botão de "Adicionar" se já existir a configuração (para evitar duplicações)
    def has_add_permission(self, request):
        if ConfiguracaoPonto.objects.exists():
            return False
        return super().has_add_permission(request)

@admin.register(RegistroPonto)
class RegistroPontoAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'data', 'entrada', 'saida_almoco', 'retorno_almoco', 'saida', 'ip_registrado')
    list_filter = ('data', 'funcionario')
    search_fields = ('funcionario__user__first_name', 'ip_registrado')