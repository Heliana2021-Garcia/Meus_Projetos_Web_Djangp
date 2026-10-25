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
