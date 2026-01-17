from django.contrib import admin
from .models import VendedorRodizio

@admin.register(VendedorRodizio)
class VendedorRodizioAdmin(admin.ModelAdmin):
    list_display = ('vendedor', 'ativo', 'ultima_atribuicao', 'ordem')
    list_editable = ('ativo', 'ordem') # Permite editar direto na lista
    list_filter = ('ativo',)
    search_fields = ('vendedor__username', 'vendedor__first_name')
    ordering = ('ordem', 'ultima_atribuicao')