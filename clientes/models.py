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

    class StatusContato(models.TextChoices):
        NAO_CONTATADO = 'Nao contatado', 'Não contatado'
        TENTATIVA = 'Tentativa', 'Tentativa de contato'
        CONTATO_REALIZADO = 'Contato realizado', 'Contato realizado'
        AGUARDANDO_RETORNO = 'Aguardando retorno', 'Aguardando retorno'
        SEM_INTERESSE = 'Sem interesse', 'Sem interesse'
        FECHADO_SUCESSO = 'Fechado com sucesso', 'Fechado com sucesso'
        PERDIDO = 'Perdido', 'Perdido'

    class EtapaFunil(models.TextChoices):
        RECEPCAO = 'Recepcao', 'Recepção do lead'
        QUALIFICACAO = 'Qualificacao', 'Qualificação'
        APRESENTACAO = 'Apresentacao', 'Apresentação do veículo'
        PROPOSTA = 'Proposta', 'Proposta'
        NEGOCIACAO = 'Negociacao', 'Negociação'
        FECHAMENTO = 'Fechamento', 'Fechamento'
        POS_VENDA = 'Pos-venda', 'Pós-venda'
        ENCERRADO = 'Encerrado', 'Encerrado'

    class TipoNegociacao(models.TextChoices):
        VENDA = 'Venda', 'Venda'
        CONSIGNACAO = 'Consignacao', 'Consignação'
        OUTRO = 'Outro', 'Outro'

    TIPO_VEICULO_CHOICES = (
        ('carros', 'Carro'),
        ('motos', 'Moto'),
        ('caminhoes', 'Caminhão'),
    )

    vendedor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='clientes')
    whatsapp = models.CharField(max_length=20)
    nome_cliente = models.CharField(max_length=255)
    tipo_veiculo = models.CharField(max_length=10, choices=TIPO_VEICULO_CHOICES, default='carros', verbose_name="Tipo de Veículo")
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
    status_contato = models.CharField(
        max_length=25,
        choices=StatusContato.choices,
        default=StatusContato.NAO_CONTATADO,
        verbose_name="Status do Contato"
    )
    etapa_funil = models.CharField(
        max_length=20,
        choices=EtapaFunil.choices,
        default=EtapaFunil.RECEPCAO,
        verbose_name="Etapa do Funil"
    )
    data_ultimo_andamento = models.DateTimeField(null=True, blank=True, verbose_name="Último andamento")
    observacao = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # Se for um cliente novo, define uma data de próximo contato padrão
        if self._state.adding:
            self.data_proximo_contato = timezone.now() + timedelta(days=5)
        
        # Salva o objeto
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


class LeadAndamento(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='andamentos')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='andamentos_registrados')
    criado_em = models.DateTimeField(auto_now_add=True)
    status_contato = models.CharField(max_length=25, choices=Cliente.StatusContato.choices)
    etapa_funil = models.CharField(max_length=20, choices=Cliente.EtapaFunil.choices)
    proximo_passo = models.CharField(max_length=20, choices=Cliente.ProximoPasso.choices, blank=True, null=True)
    data_proxima_acao = models.DateTimeField(blank=True, null=True)
    comentario = models.TextField()

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Andamento do Lead'
        verbose_name_plural = 'Andamentos dos Leads'

    def __str__(self):
        return f"{self.cliente.nome_cliente} - {self.etapa_funil} ({self.criado_em:%d/%m/%Y %H:%M})"
