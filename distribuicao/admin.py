from django.contrib import admin
from .models import VendedorRodizio

@admin.register(VendedorRodizio)
class VendedorRodizioAdmin(admin.ModelAdmin):
    # Colunas que aparecem na lista
    list_display = ('vendedor', 'ativo', 'ultima_atribuicao', 'ordem')
    
    # Permite marcar/desmarcar o "Ativo" direto na lista, sem abrir o cadastro
    list_editable = ('ativo', 'ordem')
    
    # Filtros laterais
    list_filter = ('ativo',)
    
    # Campo de busca
    search_fields = ('vendedor__username', 'vendedor__first_name')
    
    # Ordenação padrão
    ordering = ('ordem', 'ultima_atribuicao')