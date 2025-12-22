from django.contrib import admin
from .models import BannerSistema

@admin.register(BannerSistema)
class BannerSistemaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'ativo', 'usar_imagem')
    list_editable = ('ativo',)