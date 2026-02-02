from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import os
import uuid

from crmspagi.storage_backends import PublicMediaStorage

User = get_user_model()

def get_comprovante_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{ext}"
    folder = instance.placa if instance.placa else 'geral'
    return f"vendas_produtos/comprovantes/{folder}/{unique_filename}"

def get_apolice_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    unique_filename = f"apolice_{uuid.uuid4()}{ext}"
    folder = instance.placa if instance.placa else 'geral'
    return f"vendas_produtos/apolices/{folder}/{unique_filename}"

# === NOVO MODELO: FECHAMENTO MENSAL ===
class FechamentoMensal(models.Model):
    mes = models.IntegerField(verbose_name="Mês")
    ano = models.IntegerField(verbose_name="Ano")
    data_fechamento = models.DateTimeField(auto_now=True, verbose_name="Data do Fechamento")
    responsavel = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Fechado por")
    
    class Meta:
        unique_together = ['mes', 'ano']
        verbose_name = "Fechamento Mensal"
        verbose_name_plural = "Fechamentos Mensais"

    def __str__(self):
        return f"Fechamento {self.mes}/{self.ano}"

class VendaProduto(models.Model):
    TIPO_CHOICES = [
        ('VENDA_VEICULO', 'Venda de Veículo'),
        ('GARANTIA', 'Seguro Garantia (Mecânica)'),
        ('SEGURO', 'Seguro Veículo (Novo)'),
        ('TRANSFERENCIA', 'Transferência / Despachante'),
        ('REFINANCIAMENTO', 'Refinanciamento de Veículo'),
    ]

    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente de Conferência'),
        ('APROVADO', 'Aprovado pelo Gerente'),
        ('REJEITADO', 'Rejeitado'),
    ]

    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vendas_produtos')
    gerente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='conferencias_produtos')
    
    # === CAMPO NOVO: AJUDANTE ===
    vendedor_ajudante = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='vendas_ajudadas',
        verbose_name="Vendedor Ajudante (Split)"
    )
    comissao_ajudante = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        editable=False
    )

    # === DADOS DO VEÍCULO / CLIENTE ===
    cliente_nome = models.CharField(max_length=150, verbose_name="Nome do Cliente")
    placa = models.CharField(max_length=10)
    modelo_veiculo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Modelo")
    cor = models.CharField(max_length=50, blank=True, null=True, verbose_name="Cor")
    ano = models.CharField(max_length=9, blank=True, null=True, verbose_name="Ano (Ex: 2023/2024)")
    
    tipo_produto = models.CharField(max_length=20, choices=TIPO_CHOICES)
    
    # === FINANCEIRO GERAL ===
    pgto_pix = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor em Pix")
    pgto_transferencia = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor em Transferência")
    pgto_debito = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor no Débito")
    pgto_credito = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor no Crédito")
    pgto_financiamento = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor Financiado")
    
    com_desconto = models.BooleanField(default=False, verbose_name="Houve desconto na venda?")

    comprovante = models.FileField(
        upload_to=get_comprovante_upload_path,
        storage=PublicMediaStorage(), 
        blank=True, 
        null=True,
        verbose_name="Comprovante de Pagamento"
    )
    
    banco_financiamento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Banco Financiador")
    numero_proposta = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nº da Proposta")

    # === CAMPOS ESPECÍFICOS DE REFINANCIAMENTO ===
    qtd_parcelas = models.IntegerField(null=True, blank=True, verbose_name="Qtd. Parcelas")
    valor_parcela = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor da Parcela")
    valor_retorno_operacao = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Retorno da Operação")
    # ============================================

    numero_apolice = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nº da Apólice")
    arquivo_apolice = models.FileField(
        upload_to=get_apolice_upload_path,
        storage=PublicMediaStorage(),
        blank=True, 
        null=True,
        verbose_name="PDF da Apólice"
    )

    custo_base = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Custo Real / Base")
    valor_venda = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Cobrado do Cliente")
    
    comissao_vendedor = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    lucro_loja = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDENTE')
    motivo_recusa = models.TextField(blank=True, null=True, verbose_name="Motivo da Recusa")
    
    data_venda = models.DateField(default=timezone.now, verbose_name="Data da Venda")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")
    
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_aprovacao = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Venda de Produto/Serviço"
        verbose_name_plural = "Vendas de Produtos"
        ordering = ['-data_venda', '-data_criacao']

    def clean(self):
        hoje = timezone.now().date()
        data_lancamento = self.data_venda
        if isinstance(data_lancamento, timezone.datetime):
             data_lancamento = data_lancamento.date()

        # --- ALTERADO: VERIFICA SE O MÊS ESTÁ FECHADO ---
        if FechamentoMensal.objects.filter(mes=data_lancamento.month, ano=data_lancamento.year).exists():
            raise ValidationError(f"O mês {data_lancamento.month}/{data_lancamento.year} está FECHADO. Não é possível lançar ou alterar vendas neste período.")
        
        # REMOVIDA A TRAVA DE DATA RETROATIVA SIMPLES (if self._state.adding and data_lancamento < hoje...)

        # VALIDAÇÃO GERAL
        if not self.modelo_veiculo:
            raise ValidationError({'modelo_veiculo': 'O Modelo do Veículo é obrigatório.'})
        if not self.placa:
            raise ValidationError({'placa': 'A Placa do Veículo é obrigatória.'})

        if self.tipo_produto == 'GARANTIA' and self.valor_venda < 1300:
            raise ValidationError({'valor_venda': 'O valor mínimo para Seguro Garantia é R$ 1.300,00.'})
        
        if self.tipo_produto != 'REFINANCIAMENTO':
            total_pagamentos = (
                (self.pgto_pix or 0) + 
                (self.pgto_transferencia or 0) + 
                (self.pgto_debito or 0) + 
                (self.pgto_credito or 0) + 
                (self.pgto_financiamento or 0)
            )
            
            if self.valor_venda > 0 and abs(total_pagamentos - self.valor_venda) > Decimal('0.05'):
                 raise ValidationError(f"A soma dos pagamentos (R$ {total_pagamentos}) não bate com o Valor Total (R$ {self.valor_venda}).")

        # Validações condicionais
        if self.pgto_financiamento > 0 or self.tipo_produto == 'REFINANCIAMENTO':
            if not self.banco_financiamento:
                raise ValidationError({'banco_financiamento': 'Informe o Banco.'})
            if not self.numero_proposta:
                raise ValidationError({'numero_proposta': 'Informe a Proposta.'})
        
        if self.tipo_produto == 'REFINANCIAMENTO':
            if not self.qtd_parcelas:
                raise ValidationError({'qtd_parcelas': 'Informe a Qtd. de Parcelas.'})
            if not self.valor_parcela:
                raise ValidationError({'valor_parcela': 'Informe o Valor da Parcela.'})
        
        if (self.pgto_pix > 0 or self.pgto_transferencia > 0) and not self.comprovante:
             raise ValidationError({'comprovante': 'Comprovante obrigatório para Pix/Transferência.'})

    def save(self, *args, **kwargs):
        # Lógica de Cálculo de Comissão
        if self.tipo_produto == 'VENDA_VEICULO':
            self.custo_base = Decimal('0.00')
            self.lucro_loja = Decimal('0.00')
            self.comissao_ajudante = Decimal('0.00')
            if self.com_desconto:
                self.comissao_vendedor = Decimal('200.00')
            else:
                self.comissao_vendedor = Decimal('500.00')

        elif self.tipo_produto == 'GARANTIA':
            custo_real_provider = Decimal('997.00')
            preco_base_loja = Decimal('1300.00')
            self.custo_base = custo_real_provider
            self.lucro_loja = preco_base_loja - custo_real_provider
            self.comissao_ajudante = Decimal('0.00')
            
            if self.valor_venda >= preco_base_loja:
                self.comissao_vendedor = self.valor_venda - preco_base_loja
            else:
                self.comissao_vendedor = Decimal('0.00')

        elif self.tipo_produto == 'SEGURO':
            referencia_comissao = Decimal('150.00')
            self.custo_base = Decimal('0.00')
            self.comissao_ajudante = Decimal('0.00')
            if self.valor_venda >= 299:
                self.comissao_vendedor = referencia_comissao
                self.lucro_loja = self.valor_venda 
            else:
                self.comissao_vendedor = referencia_comissao * Decimal('0.40')
                self.lucro_loja = referencia_comissao * Decimal('0.60')

        elif self.tipo_produto == 'TRANSFERENCIA':
            lucro_operacao = self.valor_venda - self.custo_base
            self.comissao_ajudante = Decimal('0.00')
            if lucro_operacao > 0:
                self.lucro_loja = lucro_operacao * Decimal('0.70')
                self.comissao_vendedor = lucro_operacao * Decimal('0.30')
            else:
                self.lucro_loja = Decimal('0.00')
                self.comissao_vendedor = Decimal('0.00')

        elif self.tipo_produto == 'REFINANCIAMENTO':
            # REGRA: Valor Cobrado (valor_venda) -> 30% Vendedor / 70% Loja
            base_calculo = self.valor_venda
            self.custo_base = Decimal('0.00') 
            
            if base_calculo > 0:
                comissao_total = base_calculo * Decimal('0.30')
                self.lucro_loja = base_calculo * Decimal('0.70')

                # LÓGICA DE SPLIT (AJUDANTE)
                if self.vendedor_ajudante:
                    self.comissao_vendedor = comissao_total * Decimal('0.50')
                    self.comissao_ajudante = comissao_total * Decimal('0.50')
                else:
                    self.comissao_vendedor = comissao_total
                    self.comissao_ajudante = Decimal('0.00')
            else:
                self.comissao_vendedor = Decimal('0.00')
                self.comissao_ajudante = Decimal('0.00')
                self.lucro_loja = Decimal('0.00')

        super().save(*args, **kwargs)

    @property
    def resumo_pagamento(self):
        if self.tipo_produto == 'REFINANCIAMENTO':
            return f"Refin: {self.qtd_parcelas}x R${self.valor_parcela} (Fin: {self.pgto_financiamento})"

        metodos = []
        if self.pgto_pix > 0: metodos.append(f"Pix ({self.pgto_pix})")
        if self.pgto_transferencia > 0: metodos.append(f"Transf ({self.pgto_transferencia})")
        if self.pgto_debito > 0: metodos.append(f"Débito ({self.pgto_debito})")
        if self.pgto_credito > 0: metodos.append(f"Crédito ({self.pgto_credito})")
        if self.pgto_financiamento > 0: metodos.append(f"Finan ({self.pgto_financiamento})")
        return ", ".join(metodos)