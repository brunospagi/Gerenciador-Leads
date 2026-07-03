from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Funcionario

# Inline para editar Funcionario dentro da tela de Usuario
class FuncionarioInline(admin.StackedInline):
    model = Funcionario
    can_delete = False
    verbose_name_plural = 'Dados Funcionais (RH)'
    fk_name = 'user'

# Personaliza o Admin de Usuários
class UserAdmin(BaseUserAdmin):
    inlines = (FuncionarioInline,)
    list_display = ('username', 'first_name', 'last_name', 'get_cargo', 'is_staff')
    
    def get_cargo(self, instance):
        return instance.dados_funcionais.cargo if hasattr(instance, 'dados_funcionais') else '-'
    get_cargo.short_description = 'Cargo'

# Registra o novo UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

class CpfPendenteFilter(admin.SimpleListFilter):
    title = 'CPF pendente'
    parameter_name = 'cpf_pendente'

    def lookups(self, request, model_admin):
        return (('sim', 'Pendente (placeholder)'), ('nao', 'Preenchido'))

    def queryset(self, request, queryset):
        if self.value() not in ('sim', 'nao'):
            return queryset
        ids_pendentes = [f.pk for f in queryset if f.cpf_pendente]
        if self.value() == 'sim':
            return queryset.filter(pk__in=ids_pendentes)
        return queryset.exclude(pk__in=ids_pendentes)


# Admin isolado de Funcionários (para listagem rápida)
@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ('get_nome', 'cargo', 'salario_base', 'telefone', 'ativo', 'get_cpf_pendente', 'data_ultimo_dia_trabalhado')
    search_fields = ('user__username', 'user__first_name', 'cpf')
    list_filter = ('ativo', 'cargo', CpfPendenteFilter)

    def get_nome(self, obj):
        return obj.nome_completo
    get_nome.short_description = 'Colaborador'
    get_nome.admin_order_field = 'user__first_name'

    def get_cpf_pendente(self, obj):
        return obj.cpf_pendente
    get_cpf_pendente.short_description = 'CPF pendente'
    get_cpf_pendente.boolean = True
