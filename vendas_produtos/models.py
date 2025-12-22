from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import os
import uuid

# Importa a classe de armazenamento configurada (MinIO ou S3)
from crmspagi.storage_backends import PublicMediaStorage

User = get_user_model()

def get_comprovante_upload_path(instance, filename):
    """Gera nome único para o arquivo no MinIO"""
    ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{ext}"
    folder = instance.placa if instance.placa else 'geral'
    return f"vendas_produtos/{folder}/{unique_filename}"

class VendaProduto(models.Model):
    # --- OPÇÕES ---
    TIPO_CHOICES = [
        ('GARANTIA', 'Seguro Garantia (Mecânica)'),
        ('SEGURO', 'Seguro Veículo (Novo)'),
        ('TRANSFERENCIA', 'Transferência / Despachante'),
    ]

    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente de Conferência'),
        ('APROVADO', 'Aprovado pelo Gerente'),
        ('REJEITADO', 'Rejeitado'),
    ]

    PAGAMENTO_CHOICES = [
        ('PIX', 'Pix'),
        ('TRANSFERENCIA', 'Transferência Bancária'),
        ('DEBITO', 'Cartão de Débito'),
        ('CREDITO', 'Cartão de Crédito'),
        ('FINANCIAMENTO', 'Incluso no Financiamento'),
    ]

    # --- VÍNCULOS ---
    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vendas_produtos')
    gerente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='conferencias_produtos')
    
    # --- DADOS ---
    placa = models.CharField(max_length=10)
    cliente_nome = models.CharField(max_length=150, verbose_name="Nome do Cliente")
    tipo_produto = models.CharField(max_length=20, choices=TIPO_CHOICES)
    
    forma_pagamento = models.CharField(max_length=20, choices=PAGAMENTO_CHOICES, default='PIX', verbose_name="Forma de Pagamento")
    
    # Upload MinIO
    comprovante = models.FileField(
        upload_to=get_comprovante_upload_path,
        storage=PublicMediaStorage(), 
        blank=True, 
        null=True, 
        verbose_name="Comprovante de Pagamento"
    )
    
    banco_financiamento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Banco Financiador")
    numero_proposta = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nº da Proposta")

    # --- VALORES ---
    custo_base = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Custo Real / Base")
    valor_venda = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Cobrado do Cliente")
    
    # --- RESULTADOS ---
    comissao_vendedor = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    lucro_loja = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    
    # --- CONTROLE ---
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

        # Validação Retroativa
        if self._state.adding and data_lancamento < hoje:
            raise ValidationError("Não é permitido lançar vendas com data retroativa.")

        # Validação Garantia
        if self.tipo_produto == 'GARANTIA':
            if self.valor_venda < 1300:
                raise ValidationError({'valor_venda': 'O valor mínimo para Seguro Garantia é R$ 1.300,00.'})

        # Validação Pagamento (Apenas se valor > 0)
        if self.valor_venda > 0:
            if self.forma_pagamento == 'FINANCIAMENTO':
                if not self.banco_financiamento:
                    raise ValidationError({'banco_financiamento': 'Informe o Banco.'})
                if not self.numero_proposta:
                    raise ValidationError({'numero_proposta': 'Informe a Proposta.'})
            else:
                if not self.comprovante:
                    raise ValidationError({'comprovante': 'O comprovante é obrigatório.'})

    def save(self, *args, **kwargs):
        # --- 1. SEGURO GARANTIA ---
        if self.tipo_produto == 'GARANTIA':
            custo_real_provider = Decimal('997.00')
            preco_base_loja = Decimal('1300.00')
            self.custo_base = custo_real_provider
            
            self.lucro_loja = preco_base_loja - custo_real_provider
            
            if self.valor_venda >= preco_base_loja:
                self.comissao_vendedor = self.valor_venda - preco_base_loja
            else:
                self.comissao_vendedor = Decimal('0.00')

        # --- 2. SEGURO VEÍCULO (AJUSTADO) ---
        elif self.tipo_produto == 'SEGURO':
            referencia_comissao = Decimal('150.00')
            self.custo_base = Decimal('0.00')
            
            if self.valor_venda >= 299:
                # COM ADESÃO:
                # Vendedor ganha R$ 150 fixo (externo).
                self.comissao_vendedor = referencia_comissao
                
                # Loja fica com TODA a adesão (Ex: 299,00). Não desconta os 150.
                self.lucro_loja = self.valor_venda 
            else:
                # SEM ADESÃO (R$ 0,00 ou parcial):
                # Percentual sobre a base de 150
                self.comissao_vendedor = referencia_comissao * Decimal('0.40') # 60.00
                self.lucro_loja = referencia_comissao * Decimal('0.60')        # 90.00

        # --- 3. TRANSFERÊNCIA ---
        elif self.tipo_produto == 'TRANSFERENCIA':
            lucro_operacao = self.valor_venda - self.custo_base
            if lucro_operacao > 0:
                self.lucro_loja = lucro_operacao * Decimal('0.70')
                self.comissao_vendedor = lucro_operacao * Decimal('0.30')
            else:
                self.lucro_loja = Decimal('0.00')
                self.comissao_vendedor = Decimal('0.00')

        super().save(*args, **kwargs)

    @property
    def comprovante_url(self):
        if self.comprovante:
            return self.comprovante.url
        return '#'