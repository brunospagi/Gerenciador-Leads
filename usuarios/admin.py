from django.contrib import admin
from .models import Profile, UserLoginActivity

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    # Mostra se pode distribuir na listagem
    list_display = ('user', 'nivel_acesso', 'pode_distribuir_leads') 
    
    # Permite marcar a caixinha sem abrir o perfil (agilidade)
    list_editable = ('pode_distribuir_leads',) 
    
    list_filter = ('nivel_acesso', 'pode_distribuir_leads')
    search_fields = ('user__username', 'user__first_name', 'user__email')

@admin.register(UserLoginActivity)
class UserLoginActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_timestamp', 'ip_address')
    readonly_fields = ('user', 'login_timestamp', 'ip_address')
    list_filter = ('login_timestamp',)