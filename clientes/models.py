from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

class Cliente(models.Model):
    class TipoContato(models.TextChoices):
        MENSAGEM = 'Mensagem', 'Mensagem'
        AUDIO = 'Audio', 'Áudio'
        VIDEO = 'Video', 'Vídeo'
        LIGACAO = 'Ligacao', 'Ligação'
        OUTRO = 'Outro', 'Outro'

    class StatusNegociacao(models.TextChoices):
        NOVO = 'Novo', 'Novo'
        PENDENTE = 'Pendente', 'Pendente'
        EM_ATENDIMENTO = 'Em atendimento', 'Em atendimento'
        AGENDADO = 'Agendado', 'Agendado'
        VENDIDO = 'Vendido', 'Vendido'
        FECHAMENTO = 'Fechamento', 'Fechamento'
        SEM_RESPOSTA = 'Sem resposta', 'Sem resposta'
        FINALIZADO = 'Finalizado', 'Finalizado'

    class ProximoPasso(models.TextChoices):
        AUDIO = 'Audio', 'Áudio'
        MENSAGEM = 'Mensagem', 'Mensagem'
        LIGACAO = 'Ligacao', 'Ligação'
        VIDEO = 'Video', 'Vídeo'
        OUTRO = 'Outro', 'Outro'
    
    class Prioridade(models.TextChoices):
        FRIO = 'Frio', 'Frio'
        MORNO = 'Morno', 'Morno'
        QUENTE = 'Quente', 'Quente'

    class TipoNegociacao(models.TextChoices):
        VENDA = 'Venda', 'Venda'
        CONSIGNACAO = 'Consignacao', 'Consignação'
        OUTRO = 'Outro', 'Outro'

    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='clientes')
    whatsapp = models.CharField(max_length=20)
    nome_cliente = models.CharField(max_length=255)
    marca_veiculo = models.CharField(max_length=100, verbose_name="Marca do Veículo", blank=True, null=True)
    modelo_veiculo = models.CharField(max_length=100, verbose_name="Modelo do Veículo", blank=True, null=True)
    ano_veiculo = models.CharField(max_length=20, verbose_name="Ano do Veículo", blank=True, null=True)
    
    valor_estimado_veiculo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Valor Estimado do Veículo")
    fonte_cliente = models.CharField(max_length=100, blank=True, null=True, verbose_name="Fonte do Cliente")
    quantidade_ligacoes = models.IntegerField(default=0, verbose_name="Quantidade de Ligações")
    
    tipo_negociacao = models.CharField(
        max_length=20, 
        choices=TipoNegociacao.choices, 
        default=TipoNegociacao.VENDA, 
        verbose_name="Tipo de Negociação"
    )

    data_primeiro_contato = models.DateTimeField(auto_now_add=True)
    data_ultimo_contato = models.DateTimeField(auto_now=True)
    data_proximo_contato = models.DateTimeField()
    tipo_contato = models.CharField(max_length=20, choices=TipoContato.choices)
    status_negociacao = models.CharField(max_length=20, choices=StatusNegociacao.choices, default=StatusNegociacao.NOVO)
    proximo_passo = models.CharField(max_length=20, choices=ProximoPasso.choices)
    prioridade = models.CharField(max_length=10, choices=Prioridade.choices, default=Prioridade.MORNO)
    observacao = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if not is_new:
            original = Cliente.objects.get(pk=self.pk)
            if original.status_negociacao != self.status_negociacao:
                if self.status_negociacao == self.StatusNegociacao.AGENDADO:
                    data_formatada = self.data_proximo_contato.strftime('%d/%m/%Y às %H:%M')
                    motivacao = f"Visita agendada para {data_formatada} pelo vendedor {self.vendedor.username}."
                    Historico.objects.create(
                        cliente=self,
                        motivacao=motivacao
                    )
                else:  # Para qualquer outra mudança de status, mantém a mensagem padrão
                    Historico.objects.create(
                        cliente=self,
                        motivacao=f"Status alterado de '{original.get_status_negociacao_display()}' para '{self.get_status_negociacao_display()}'."
                    )
        
        # Define uma data de próximo contato padrão apenas se o cliente for novo
        if is_new:
            self.data_proximo_contato = timezone.now() + timedelta(days=5)
            
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome_cliente

    @property
    def contato_atrasado(self):
        if self.data_proximo_contato:
            return timezone.now() > self.data_proximo_contato
        return False

class Historico(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='historico')
    data_interacao = models.DateTimeField(auto_now_add=True)
    motivacao = models.TextField()

    class Meta:
        ordering = ['-data_interacao']

    def __str__(self):
        return f"Histórico de {self.cliente.nome_cliente} em {self.data_interacao.strftime('%d/%m/%Y')}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)