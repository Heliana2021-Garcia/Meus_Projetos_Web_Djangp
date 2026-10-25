from django.conf import settings
from django.db import models


class ModeloBase(models.Model):
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True


class Tecnologia(ModeloBase):
    nome = models.CharField("nome", max_length=60, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "tecnologia"
        verbose_name_plural = "tecnologias"

    def __str__(self):
        return self.nome


class Notificacao(ModeloBase):
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificacoes",
        verbose_name="destinatário",
    )
    titulo = models.CharField("título", max_length=120)
    mensagem = models.TextField("mensagem", blank=True)
    url = models.CharField("ligação", max_length=200, blank=True)
    lida = models.BooleanField("lida", default=False)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "notificação"
        verbose_name_plural = "notificações"

    def __str__(self):
        return f"{self.titulo} → {self.destinatario}"