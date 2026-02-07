from django.contrib import admin
from .models import Desconto, ParcelaDesconto, FolhaPagamento

class ParcelaInline(admin.TabularInline):
    model = ParcelaDesconto
    extra = 0
    readonly_fields = ('processada_na_folha',)

@admin.register(Desconto)
class DescontoAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'funcionario', 'valor_total', 'qtd_parcelas', 'data_lancamento')
    inlines = [ParcelaInline]

@admin.register(FolhaPagamento)
class FolhaPagamentoAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'mes', 'ano', 'salario_base', 'total_comissoes', 'total_descontos', 'salario_liquido', 'fechada')
    list_filter = ('mes', 'ano', 'fechada')
    actions = ['recalcular_folha']

    def recalcular_folha(self, request, queryset):
        for folha in queryset:
            if not folha.fechada:
                folha.calcular_folha()
    recalcular_folha.short_description = "Recalcular valores (se aberta)"