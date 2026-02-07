from django.contrib import admin
from .models import VendaProduto, FechamentoMensal, ParametrosComissao

@admin.register(ParametrosComissao)
class ParametrosComissaoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'comissao_carro_padrao', 'comissao_moto', 'split_refin')
    
    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(VendaProduto)
class VendaProdutoAdmin(admin.ModelAdmin):
    list_display = ('tipo_produto', 'modelo_veiculo', 'placa', 'vendedor', 'data_venda', 'status', 'comissao_vendedor')
    list_filter = ('tipo_produto', 'status', 'data_venda')
    search_fields = ('placa', 'modelo_veiculo', 'cliente_nome')

@admin.register(FechamentoMensal)
class FechamentoMensalAdmin(admin.ModelAdmin):
    list_display = ('mes', 'ano', 'responsavel', 'data_fechamento')
    list_filter = ('ano',)