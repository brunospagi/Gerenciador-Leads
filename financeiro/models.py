from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model

from folha_pagamento.models import FolhaPagamento
from vendas_produtos.models import VendaProduto

User = get_user_model()

class TransacaoFinanceira(models.Model):
    TIPO_CHOICES = [
        ('RECEITA', 'Receita / Crédito'),
        ('DESPESA', 'Despesa / Conta'),
    ]

    CATEGORIA_CHOICES = [
        ('FIXA', 'Conta Fixa (Água, Luz, Aluguel)'),
        ('VARIAVEL', 'Despesa Variável (Limpeza, Material)'),
        ('VEICULO', 'Despesa com Veículo (Oficina, Peças)'),
        ('RETORNO_FIN', 'Retorno de Financiamento'),
        ('BONUS', 'Bônus / Premiação'),
        ('OUTROS', 'Outros'),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name="Tipo de Transação")
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, verbose_name="Categoria")
    descricao = models.CharField(max_length=255, verbose_name="Descrição")
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")
    
    data_vencimento = models.DateField(default=timezone.now, verbose_name="Data de Vencimento/Recebimento")
    data_pagamento = models.DateField(null=True, blank=True, verbose_name="Data Efetiva (Pago/Recebido)")
    efetivado = models.BooleanField(default=False, verbose_name="Efetivado?")
    recorrente = models.BooleanField(default=False, verbose_name="Conta Fixa Mensal? (Repetir mês seguinte)")

    # Quem lançou a conta no sistema
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Lançado por")

    # Campos de Veículos
    placa = models.CharField(max_length=10, blank=True, null=True, verbose_name="Placa do Veículo")
    modelo_veiculo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Modelo")
    ano = models.CharField(max_length=9, blank=True, null=True, verbose_name="Ano")

    class Meta:
        verbose_name = "Transação Financeira"
        verbose_name_plural = "Transações Financeiras"
        ordering = ['data_vencimento']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.descricao} (R$ {self.valor})"

    def clean(self):
        if self.categoria == 'VEICULO':
            if not self.placa:
                raise ValidationError({'placa': 'A Placa é obrigatória para despesas de veículos.'})
            if not self.modelo_veiculo:
                raise ValidationError({'modelo_veiculo': 'O Modelo é obrigatório para despesas de veículos.'})
            if not self.ano:
                raise ValidationError({'ano': 'O Ano é obrigatório para despesas de veículos.'})

    def save(self, *args, **kwargs):
        if self.pk:
            old_obj = TransacaoFinanceira.objects.get(pk=self.pk)
            # Duplica a conta para o próximo mês se for recorrente e acabou de ser paga
            if not old_obj.efetivado and self.efetivado and self.recorrente:
                nova_data_vencimento = self.data_vencimento + relativedelta(months=1)
                TransacaoFinanceira.objects.create(
                    tipo=self.tipo,
                    categoria=self.categoria,
                    descricao=self.descricao,
                    valor=self.valor,
                    data_vencimento=nova_data_vencimento,
                    efetivado=False,
                    recorrente=True,
                    placa=self.placa,
                    modelo_veiculo=self.modelo_veiculo,
                    ano=self.ano,
                    criado_por=self.criado_por # Mantém o autor na conta duplicada
                )
        super().save(*args, **kwargs)


def gerar_relatorio_DRE_mensal(mes, ano):
    """Calcula o lucro final e retorna os detalhes de cada transação."""
    
    # 1. Receitas de Vendas (Detalhado)
    vendas = VendaProduto.objects.filter(data_venda__month=mes, data_venda__year=ano, status='APROVADO').order_by('data_venda')
    lucro_vendas = vendas.aggregate(Sum('lucro_loja'))['lucro_loja__sum'] or 0

    # 2. Receitas Extras (Detalhado)
    receitas_list = TransacaoFinanceira.objects.filter(
        tipo='RECEITA', efetivado=True, data_pagamento__month=mes, data_pagamento__year=ano
    ).order_by('data_pagamento')
    receitas_extras = receitas_list.aggregate(Sum('valor'))['valor__sum'] or 0

    total_entradas = lucro_vendas + receitas_extras

    # 3. Despesas da Loja (Detalhado)
    despesas_list = TransacaoFinanceira.objects.filter(
        tipo='DESPESA', efetivado=True, data_pagamento__month=mes, data_pagamento__year=ano
    ).order_by('data_pagamento')
    despesas_loja = despesas_list.aggregate(Sum('valor'))['valor__sum'] or 0

    # 4. Despesas de RH (Detalhado)
    folhas_list = FolhaPagamento.objects.filter(mes=mes, ano=ano).select_related('funcionario')
    agregado_rh = folhas_list.aggregate(
        total_base=Sum('salario_base'),
        total_bonus=Sum('total_creditos_manuais')
    )
    custo_salario = agregado_rh['total_base'] or 0
    custo_bonus = agregado_rh['total_bonus'] or 0
    custo_rh = custo_salario + custo_bonus

    total_saidas = despesas_loja + custo_rh

    return {
        'mes': mes, 'ano': ano,
        'vendas_list': vendas,
        'lucro_vendas': lucro_vendas,
        'receitas_list': receitas_list,
        'receitas_extras': receitas_extras,
        'total_entradas': total_entradas,
        'despesas_list': despesas_list,
        'despesas_loja': despesas_loja,
        'folhas_list': folhas_list,
        'custo_salario': custo_salario,
        'custo_bonus': custo_bonus,
        'custo_rh': custo_rh,
        'total_saidas': total_saidas,
        'saldo_liquido': total_entradas - total_saidas
    }