from django.contrib import admin
from .models import TransacaoFinanceira

@admin.register(TransacaoFinanceira)
class TransacaoFinanceiraAdmin(admin.ModelAdmin):
    # O que aparece nas colunas da lista
    list_display = (
        'descricao', 
        'tipo', 
        'categoria', 
        'valor', 
        'data_vencimento', 
        'efetivado', 
        'criado_por'
    )
    
    # Filtros laterais direitos
    list_filter = (
        'tipo', 
        'categoria', 
        'efetivado', 
        'recorrente', 
        'data_vencimento', 
        'criado_por'
    )
    
    # Barra de pesquisa
    search_fields = ('descricao', 'placa', 'modelo_veiculo', 'criado_por__username', 'criado_por__first_name')
    
    # Navegação por datas no topo
    date_hierarchy = 'data_vencimento'
    
    # Permite alterar o status de "Efetivado" diretamente na lista sem entrar no registo
    list_editable = ('efetivado',)
    
    # Organização do formulário em blocos (Fieldsets)
    fieldsets = (
        ('Informações Principais', {
            'fields': ('tipo', 'categoria', 'descricao', 'valor', 'criado_por')
        }),
        ('Datas e Status', {
            'fields': ('data_vencimento', 'data_pagamento', 'efetivado', 'recorrente'),
            'description': 'Atenção: Se for "Conta Fixa" e marcar como "Efetivado", o sistema irá gerar a conta do próximo mês automaticamente.'
        }),
        ('Dados do Veículo (Apenas se categoria for VEICULO)', {
            'fields': ('placa', 'modelo_veiculo', 'ano'),
            'classes': ('collapse',), # Oculta esta secção por defeito (clique para expandir)
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Sobrescreve a função de guardar para garantir que, 
        se o ADMIN não selecionar quem criou a conta, 
        o sistema atribua automaticamente o utilizador que está logado no momento.
        """
        if not obj.criado_por:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)