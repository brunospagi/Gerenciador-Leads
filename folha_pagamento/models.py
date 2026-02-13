from django.db import models
from django.utils import timezone
from funcionarios.models import Funcionario
from vendas_produtos.models import VendaProduto
from django.db.models import Sum, Q
from decimal import Decimal
import calendar

# === 1. FERIADOS ===
class Feriado(models.Model):
    descricao = models.CharField(max_length=100, verbose_name="Descrição do Feriado")
    data = models.DateField(verbose_name="Data")
    fixo = models.BooleanField(default=False, verbose_name="Feriado Fixo? (Repete todo ano)")

    def __str__(self):
        tipo = "Fixo" if self.fixo else "Variável"
        return f"{self.data.strftime('%d/%m')} - {self.descricao} ({tipo})"

    class Meta:
        ordering = ['data']
        verbose_name = "Feriado"
        verbose_name_plural = "Feriados"

# === 2. CRÉDITOS MANUAIS (BÔNUS, REEMBOLSOS) ===
class Credito(models.Model):
    TIPO_CHOICES = [
        ('BONUS', 'Bonificação / Prêmio'),
        ('REEMBOLSO', 'Reembolso de Despesas'),
        ('HORA_EXTRA', 'Horas Extras'),
        ('OUTROS', 'Outros Créditos'),
    ]

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='creditos')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Total")
    data_lancamento = models.DateField(default=timezone.now)
    
    # Parcelamento
    parcelado = models.BooleanField(default=False, verbose_name="Parcelar?")
    qtd_parcelas = models.IntegerField(default=1, verbose_name="Qtd. Parcelas")
    mes_inicio = models.IntegerField(verbose_name="Mês Início (1-12)", default=timezone.now().month)
    ano_inicio = models.IntegerField(verbose_name="Ano Início", default=timezone.now().year)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Gera parcelas automaticamente na criação
        if is_new:
            valor_parcela = self.valor_total / self.qtd_parcelas
            mes_atual = self.mes_inicio
            ano_atual = self.ano_inicio

            for i in range(self.qtd_parcelas):
                if mes_atual > 12:
                    mes_atual = 1
                    ano_atual += 1
                
                ParcelaCredito.objects.create(
                    credito_pai=self,
                    numero_parcela=i+1,
                    valor=valor_parcela,
                    mes_referencia=mes_atual,
                    ano_referencia=ano_atual
                )
                mes_atual += 1

    def __str__(self):
        return f"CRÉDITO: {self.get_tipo_display()} - {self.funcionario.user.username}"

class ParcelaCredito(models.Model):
    credito_pai = models.ForeignKey(Credito, on_delete=models.CASCADE, related_name='parcelas')
    numero_parcela = models.IntegerField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    mes_referencia = models.IntegerField()
    ano_referencia = models.IntegerField()
    processada_na_folha = models.BooleanField(default=False)

    class Meta:
        ordering = ['ano_referencia', 'mes_referencia']

# === 3. DESCONTOS MANUAIS (VALES, FALTAS) ===
class Desconto(models.Model):
    TIPO_CHOICES = [
        ('VALE', 'Vale / Adiantamento'),
        ('ATRASO', 'Faltas / Atrasos'),
        ('BENEFICIO', 'Convênio / Benefício'),
        ('OUTROS', 'Outros'),
    ]

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='descontos')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Total")
    data_lancamento = models.DateField(default=timezone.now)
    
    # Parcelamento
    parcelado = models.BooleanField(default=False, verbose_name="Parcelar?")
    qtd_parcelas = models.IntegerField(default=1, verbose_name="Qtd. Parcelas")
    mes_inicio = models.IntegerField(verbose_name="Mês Início (1-12)", default=timezone.now().month)
    ano_inicio = models.IntegerField(verbose_name="Ano Início", default=timezone.now().year)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            valor_parcela = self.valor_total / self.qtd_parcelas
            mes_atual = self.mes_inicio
            ano_atual = self.ano_inicio

            for i in range(self.qtd_parcelas):
                if mes_atual > 12:
                    mes_atual = 1
                    ano_atual += 1
                
                ParcelaDesconto.objects.create(
                    desconto_pai=self,
                    numero_parcela=i+1,
                    valor=valor_parcela,
                    mes_referencia=mes_atual,
                    ano_referencia=ano_atual
                )
                mes_atual += 1

    def __str__(self):
        return f"DESC: {self.get_tipo_display()} - {self.funcionario.user.username}"

class ParcelaDesconto(models.Model):
    desconto_pai = models.ForeignKey(Desconto, on_delete=models.CASCADE, related_name='parcelas')
    numero_parcela = models.IntegerField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    mes_referencia = models.IntegerField()
    ano_referencia = models.IntegerField()
    processada_na_folha = models.BooleanField(default=False)

    class Meta:
        ordering = ['ano_referencia', 'mes_referencia']

# === 4. FOLHA DE PAGAMENTO ===
class FolhaPagamento(models.Model):
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='folhas')
    mes = models.IntegerField()
    ano = models.IntegerField()
    data_geracao = models.DateTimeField(auto_now_add=True)
    
    # === VENCIMENTOS (CRÉDITOS) ===
    salario_base = models.DecimalField(max_digits=10, decimal_places=2)
    total_comissoes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Crédito VT (Valor integral da passagem para o funcionário)
    credito_vt = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Crédito Vale Transporte")
    
    # Outros Créditos Manuais (Bônus, etc)
    total_creditos_manuais = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Outros Créditos")

    # === DESCONTOS (DÉBITOS) ===
    total_descontos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Desconto VT (6% do salário ou custo total, o que for menor)
    desconto_vt = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Desc. Vale Transporte")
    
    # === TOTAL LÍQUIDO ===
    salario_liquido = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    fechada = models.BooleanField(default=False, verbose_name="Folha Fechada?")
    pago = models.BooleanField(default=False, verbose_name="Pago?")

    class Meta:
        unique_together = ['funcionario', 'mes', 'ano']
        ordering = ['-ano', '-mes']

    def get_dias_uteis_vt(self):
        """Conta dias de Segunda(0) a Sábado(5) excluindo Feriados."""
        cal = calendar.monthcalendar(self.ano, self.mes)
        dias_uteis = 0
        
        # Busca feriados do banco (deste ano OU fixos)
        feriados_query = Feriado.objects.filter(
            Q(data__month=self.mes, data__year=self.ano) | 
            Q(data__month=self.mes, fixo=True)
        )
        dias_feriados = set(f.data.day for f in feriados_query)

        for week in cal:
            for day_idx, day in enumerate(week):
                # day != 0: dia existe no calendário
                # day_idx < 6: Segunda a Sábado
                if day != 0 and day_idx < 6:
                    if day not in dias_feriados:
                        dias_uteis += 1
        return dias_uteis

    def calcular_folha(self):
        if self.fechada: return

        # 1. Base
        self.salario_base = self.funcionario.salario_base

        # 2. Comissões
        ultimo_dia = calendar.monthrange(self.ano, self.mes)[1]
        data_inicio = timezone.datetime(self.ano, self.mes, 1).date()
        data_fim = timezone.datetime(self.ano, self.mes, ultimo_dia).date()

        # Vendas Diretas
        vendas = VendaProduto.objects.filter(
            vendedor=self.funcionario.user,
            data_venda__range=[data_inicio, data_fim], status='APROVADO'
        )
        soma_direta = vendas.aggregate(Sum('comissao_vendedor'))['comissao_vendedor__sum'] or Decimal(0)
        
        # Vendas Ajudante
        vendas_ajudante = VendaProduto.objects.filter(
            vendedor_ajudante=self.funcionario.user,
            data_venda__range=[data_inicio, data_fim], status='APROVADO'
        )
        soma_ajudante = vendas_ajudante.aggregate(Sum('comissao_ajudante'))['comissao_ajudante__sum'] or Decimal(0)

        # --- COMISSÃO GERÊNCIA (CORRIGIDO PARA ACEITAR ADMIN TAMBÉM) ---
        comissao_gerencia = Decimal(0)
        is_gerente = False
        try:
            nivel = self.funcionario.user.profile.nivel_acesso
            if nivel == 'GERENTE' or nivel == 'ADMIN':
                is_gerente = True
        except:
            pass

        if is_gerente:
            # Vendas de OUTROS vendedores (exclude self), Aprovadas, Tipo CARRO
            qtd_carros_equipe = VendaProduto.objects.filter(
                data_venda__range=[data_inicio, data_fim], 
                status='APROVADO',
                tipo_produto='VENDA_VEICULO'
            ).exclude(vendedor=self.funcionario.user).count()

            # Vendas de OUTROS vendedores (exclude self), Aprovadas, Tipo MOTO
            qtd_motos_equipe = VendaProduto.objects.filter(
                data_venda__range=[data_inicio, data_fim], 
                status='APROVADO',
                tipo_produto='VENDA_MOTO'
            ).exclude(vendedor=self.funcionario.user).count()

            valor_por_carro = Decimal('150.00')
            valor_por_moto = Decimal('80.00')

            comissao_gerencia = (qtd_carros_equipe * valor_por_carro) + (qtd_motos_equipe * valor_por_moto)
        # ---------------------------------------------------------------

        self.total_comissoes = soma_direta + soma_ajudante + comissao_gerencia

        # 3. Créditos Manuais (Bônus)
        creditos = ParcelaCredito.objects.filter(
            credito_pai__funcionario=self.funcionario,
            mes_referencia=self.mes, ano_referencia=self.ano
        )
        self.total_creditos_manuais = creditos.aggregate(Sum('valor'))['valor__sum'] or Decimal(0)

        # 4. Descontos Manuais
        parcelas_desc = ParcelaDesconto.objects.filter(
            desconto_pai__funcionario=self.funcionario,
            mes_referencia=self.mes, ano_referencia=self.ano
        )
        total_parcelas_desc = parcelas_desc.aggregate(Sum('valor'))['valor__sum'] or Decimal(0)

        # 5. Cálculo VT (Crédito e Débito)
        self.credito_vt = Decimal(0)
        self.desconto_vt = Decimal(0)

        if self.funcionario.opta_vt:
            dias_trabalhados = self.get_dias_uteis_vt()
            custo_vt_total = dias_trabalhados * self.funcionario.valor_diario_vt
            self.credito_vt = custo_vt_total
            teto_6 = self.salario_base * Decimal('0.06')
            self.desconto_vt = min(custo_vt_total, teto_6)

        # 6. Totalizadores
        total_vencimentos = self.salario_base + self.total_comissoes + self.credito_vt + self.total_creditos_manuais
        self.total_descontos = total_parcelas_desc + self.desconto_vt

        # 7. Líquido
        self.salario_liquido = total_vencimentos - self.total_descontos
        self.save()

    def fechar(self):
        self.calcular_folha()
        
        # Marca Parcelas de Desconto como processadas
        ParcelaDesconto.objects.filter(
            desconto_pai__funcionario=self.funcionario,
            mes_referencia=self.mes, ano_referencia=self.ano
        ).update(processada_na_folha=True)

        # Marca Parcelas de Crédito como processadas
        ParcelaCredito.objects.filter(
            credito_pai__funcionario=self.funcionario,
            mes_referencia=self.mes, ano_referencia=self.ano
        ).update(processada_na_folha=True)

        self.fechada = True
        self.save()