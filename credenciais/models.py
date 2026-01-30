from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Credencial(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome do Banco/Serviço")
    link = models.URLField(max_length=500, verbose_name="Link de Acesso")
    usuario = models.CharField(max_length=200, verbose_name="Usuário/Login")
    senha = models.CharField(max_length=200, verbose_name="Senha Atual")
    observacao = models.TextField(blank=True, null=True, verbose_name="Observações (Token, Passo a passo...)")
    
    ultima_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Última Alteração")
    atualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Credencial de Acesso"
        verbose_name_plural = "Credenciais de Acesso"
        ordering = ['nome']

    def __str__(self):
        return self.nome