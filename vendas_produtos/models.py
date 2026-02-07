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

# === CONFIGURAÇÃO DE COMISSÕES (PAINEL ADMIN) ===
class ParametrosComissao(models.Model):
    # Carros
    comissao_carro_padrao = models.DecimalField(max_digits=10, decimal_places=2, default=500.00, verbose_name="Comissão Carro (Padrão)")
    comissao_carro_desconto = models.DecimalField(max_digits=10, decimal_places=2, default=200.00, verbose_name="Comissão Carro (c/ Desconto)")
    
    # Motos
    comissao_moto = models.DecimalField(max_digits=10, decimal_places=2, default=150.00, verbose_name="Comissão Moto")

    # Consignação e Compra
    comissao_consignacao = models.DecimalField(max_digits=10, decimal_places=2, default=350.00, verbose_name="Comissão Consignação/Compra")

    # Seguro Garantia
    garantia_custo = models.DecimalField(max_digits=10, decimal_places=2, default=997.00, verbose_name="Custo Garantia (Provider)")
    garantia_base = models.DecimalField(max_digits=10, decimal_places=2, default=1300.00, verbose_name="Preço Base Garantia")

    # Seguro Novo
    seguro_novo_ref = models.DecimalField(max_digits=10, decimal_places=2, default=150.00, verbose_name="Ref. Comissão Seguro Novo")
    
    # Percentuais de Split
    split_transferencia = models.DecimalField(max_digits=5, decimal_places=2, default=0.30, verbose_name="Split Transf. (Vendedor %)")
    
    # REFINANCIAMENTO (Padrão 35%)
    split_refin = models.DecimalField(max_digits=5, decimal_places=2, default=0.35, verbose_name="Split Refin. (Vendedor %)")
    
    split_ajudante = models.DecimalField(max_digits=5, decimal_places=2, default=0.50, verbose_name="Split Ajudante (%)")

    def __str__(self):
        return "Configuração Geral de Comissões"

    class Meta:
        verbose_name = "Configuração de Comissões"
        verbose_name_plural = "Configuração de Comissões"

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

# === MODELO: FECHAMENTO MENSAL ===
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
        ('VENDA_MOTO', 'Venda de Moto'),
        ('CONSIGNACAO', 'Consignação'),
        ('COMPRA', 'Compra de Veículo'),
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
    
    vendedor_ajudante = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='vendas_ajudadas',
        verbose_name="Vendedor Ajudante (Split)"
    )
    comissao_ajudante = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)

    cliente_nome = models.CharField(max_length=150, verbose_name="Nome do Cliente")
    placa = models.CharField(max_length=10)
    modelo_veiculo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Modelo")
    cor = models.CharField(max_length=50, blank=True, null=True, verbose_name="Cor")
    ano = models.CharField(max_length=9, blank=True, null=True, verbose_name="Ano (Ex: 2023/2024)")
    
    tipo_produto = models.CharField(max_length=20, choices=TIPO_CHOICES)
    
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

    qtd_parcelas = models.IntegerField(null=True, blank=True, verbose_name="Qtd. Parcelas")
    valor_parcela = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor da Parcela")
    valor_retorno_operacao = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Retorno da Operação")

    numero_apolice = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nº da Apólice")
    arquivo_apolice = models.FileField(
        upload_to=get_apolice_upload_path,
        storage=PublicMediaStorage(),
        blank=True, 
        null=True,
        verbose_name="PDF da Apólice"
    )

    custo_base = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Custo Real / Base")
    valor_venda = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor Negociado / Cobrado")
    
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

        if FechamentoMensal.objects.filter(mes=data_lancamento.month, ano=data_lancamento.year).exists():
            raise ValidationError(f"O mês {data_lancamento.month}/{data_lancamento.year} está FECHADO. Não é possível lançar ou alterar vendas neste período.")
        
        if not self.modelo_veiculo:
            raise ValidationError({'modelo_veiculo': 'O Modelo do Veículo é obrigatório.'})
        if not self.placa:
            raise ValidationError({'placa': 'A Placa do Veículo é obrigatória.'})

        if self.tipo_produto == 'GARANTIA' and self.valor_venda < 1300:
            raise ValidationError({'valor_venda': 'O valor mínimo para Seguro Garantia é R$ 1.300,00.'})
        
        tipos_flexiveis = ['REFINANCIAMENTO', 'CONSIGNACAO', 'COMPRA']
        
        if self.tipo_produto not in tipos_flexiveis:
            total_pagamentos = (
                (self.pgto_pix or 0) + 
                (self.pgto_transferencia or 0) + 
                (self.pgto_debito or 0) + 
                (self.pgto_credito or 0) + 
                (self.pgto_financiamento or 0)
            )
            
            if self.valor_venda > 0 and abs(total_pagamentos - self.valor_venda) > Decimal('0.05'):
                 raise ValidationError(f"A soma dos pagamentos (R$ {total_pagamentos}) não bate com o Valor Total (R$ {self.valor_venda}).")

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
        config = ParametrosComissao.get_solo()
        custo = self.custo_base or Decimal('0.00')
        valor = self.valor_venda or Decimal('0.00')

        # 1. VENDA (SAÍDA DE ESTOQUE) -> GERA LUCRO
        if self.tipo_produto in ['VENDA_VEICULO', 'VENDA_MOTO']:
            self.comissao_ajudante = Decimal('0.00')
            if self.tipo_produto == 'VENDA_VEICULO':
                self.comissao_vendedor = config.comissao_carro_desconto if self.com_desconto else config.comissao_carro_padrao
            else:
                self.comissao_vendedor = config.comissao_moto
            
            self.lucro_loja = valor - custo - self.comissao_vendedor

        # 2. ENTRADA (SEM LUCRO IMEDIATO)
        elif self.tipo_produto in ['CONSIGNACAO', 'COMPRA']:
            self.comissao_ajudante = Decimal('0.00')
            self.comissao_vendedor = config.comissao_consignacao
            self.lucro_loja = Decimal('0.00')

        # 3. OUTROS SERVIÇOS
        elif self.tipo_produto == 'GARANTIA':
            custo_real_provider = config.garantia_custo
            preco_base_loja = config.garantia_base
            self.custo_base = custo_real_provider
            self.lucro_loja = preco_base_loja - custo_real_provider
            self.comissao_ajudante = Decimal('0.00')
            if valor >= preco_base_loja:
                self.comissao_vendedor = valor - preco_base_loja
            else:
                self.comissao_vendedor = Decimal('0.00')

        elif self.tipo_produto == 'SEGURO':
            referencia_comissao = config.seguro_novo_ref
            self.custo_base = Decimal('0.00')
            self.comissao_ajudante = Decimal('0.00')
            if valor >= 299:
                self.comissao_vendedor = referencia_comissao
                self.lucro_loja = valor 
            else:
                self.comissao_vendedor = referencia_comissao * Decimal('0.40')
                self.lucro_loja = referencia_comissao * Decimal('0.60')

        elif self.tipo_produto == 'TRANSFERENCIA':
            lucro_operacao = valor - custo
            self.comissao_ajudante = Decimal('0.00')
            split_vendedor = config.split_transferencia
            split_loja = Decimal('1.00') - split_vendedor

            if lucro_operacao > 0:
                self.lucro_loja = lucro_operacao * split_loja
                self.comissao_vendedor = lucro_operacao * split_vendedor
            else:
                self.lucro_loja = Decimal('0.00')
                self.comissao_vendedor = Decimal('0.00')

        # 4. REFINANCIAMENTO
        elif self.tipo_produto == 'REFINANCIAMENTO':
            base_calculo = valor
            self.custo_base = Decimal('0.00') 
            
            # USA O VALOR DO ADMIN (0.35 por padrão)
            split_vendedor = config.split_refin 
            split_loja = Decimal('1.00') - split_vendedor
            
            if base_calculo > 0:
                comissao_total = base_calculo * split_vendedor
                self.lucro_loja = base_calculo * split_loja

                if self.vendedor_ajudante:
                    ajudante_pct = config.split_ajudante
                    self.comissao_vendedor = comissao_total * (Decimal('1.00') - ajudante_pct)
                    self.comissao_ajudante = comissao_total * ajudante_pct
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
        if self.tipo_produto in ['CONSIGNACAO', 'COMPRA']:
            return "Entrada de Estoque"

        metodos = []
        if self.pgto_pix > 0: metodos.append(f"Pix ({self.pgto_pix})")
        if self.pgto_transferencia > 0: metodos.append(f"Transf ({self.pgto_transferencia})")
        if self.pgto_debito > 0: metodos.append(f"Débito ({self.pgto_debito})")
        if self.pgto_credito > 0: metodos.append(f"Crédito ({self.pgto_credito})")
        if self.pgto_financiamento > 0: metodos.append(f"Finan ({self.pgto_financiamento})")
        return ", ".join(metodos)