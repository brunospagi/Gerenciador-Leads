from django.contrib import admin
from .models import FolhaPagamento, Desconto, ParcelaDesconto, Feriado, Credito, ParcelaCredito

@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ('data', 'descricao', 'fixo')
    list_filter = ('fixo', 'data')
    search_fields = ('descricao',)
    ordering = ('data',)

# --- CRÉDITOS ---
class ParcelaCreditoInline(admin.TabularInline):
    model = ParcelaCredito
    extra = 0
    readonly_fields = ('processada_na_folha',)

@admin.register(Credito)
class CreditoAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'tipo', 'valor_total', 'qtd_parcelas', 'data_lancamento')
    list_filter = ('tipo', 'data_lancamento')
    search_fields = ('funcionario__user__username', 'descricao')
    autocomplete_fields = ('funcionario',)
    date_hierarchy = 'data_lancamento'
    inlines = [ParcelaCreditoInline]

# --- DESCONTOS ---
class ParcelaDescontoInline(admin.TabularInline):
    model = ParcelaDesconto
    extra = 0
    readonly_fields = ('processada_na_folha',)

@admin.register(Desconto)
class DescontoAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'tipo', 'valor_total', 'qtd_parcelas', 'data_lancamento')
    list_filter = ('tipo', 'data_lancamento')
    search_fields = ('funcionario__user__username', 'descricao')
    autocomplete_fields = ('funcionario',)
    date_hierarchy = 'data_lancamento'
    inlines = [ParcelaDescontoInline]

@admin.register(FolhaPagamento)
class FolhaPagamentoAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'mes', 'ano', 'salario_base', 'total_comissoes', 'salario_liquido', 'fechada')
    list_filter = ('mes', 'ano', 'fechada')
    search_fields = ('funcionario__user__username',)
    autocomplete_fields = ('funcionario',)
    readonly_fields = ('data_geracao',)