from django.contrib import admin
from .models import FolhaPagamento, Desconto, ParcelaDesconto, Feriado

@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ('data', 'descricao', 'fixo')
    list_filter = ('fixo', 'data')
    search_fields = ('descricao',)
    ordering = ('data',)

class ParcelaDescontoInline(admin.TabularInline):
    model = ParcelaDesconto
    extra = 0
    readonly_fields = ('processada_na_folha',)

@admin.register(Desconto)
class DescontoAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'tipo', 'valor_total', 'qtd_parcelas', 'data_lancamento')
    list_filter = ('tipo', 'data_lancamento')
    search_fields = ('funcionario__user__username', 'descricao')
    inlines = [ParcelaDescontoInline]

@admin.register(FolhaPagamento)
class FolhaPagamentoAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'mes', 'ano', 'salario_base', 'total_comissoes', 'salario_liquido', 'fechada', 'pago')
    list_filter = ('mes', 'ano', 'fechada', 'pago')
    search_fields = ('funcionario__user__username',)
    readonly_fields = ('data_geracao',)