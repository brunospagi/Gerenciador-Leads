from django.contrib import admin
from .models import Profile, UserLoginActivity, ModulePermission

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    # Mostra se pode distribuir na listagem
    list_display = ('user', 'nivel_acesso', 'pode_distribuir_leads','pode_acessar_financeiro') 
    
    # Permite marcar a caixinha sem abrir o perfil (agilidade)
    list_editable = ('pode_distribuir_leads', 'pode_acessar_financeiro') 
    
    list_filter = ('nivel_acesso', 'pode_distribuir_leads', 'pode_acessar_financeiro')
    search_fields = ('user__username', 'user__first_name', 'user__email')

@admin.register(UserLoginActivity)
class UserLoginActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_timestamp', 'ip_address')
    readonly_fields = ('user', 'login_timestamp', 'ip_address')
    list_filter = ('login_timestamp',)


@admin.register(ModulePermission)
class ModulePermissionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'modulo_clientes',
        'modulo_vendas',
        'modulo_financeiro',
        'modulo_distribuicao',
        'modulo_rh',
        'modulo_relatorios',
        'modulo_admin_usuarios',
        'modulo_credenciais',
    )
    list_filter = ('modulo_financeiro', 'modulo_distribuicao', 'modulo_rh', 'modulo_relatorios', 'modulo_credenciais')
    search_fields = ('user__username', 'user__email', 'user__first_name')
