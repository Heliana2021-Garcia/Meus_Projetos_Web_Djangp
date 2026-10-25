from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max
from django.utils import timezone

from apps.candidaturas.models import Candidatura
from apps.core.models import ModeloBase

from . import config


class CartaEncaminhamento(ModeloBase):
    candidatura = models.OneToOneField(
        Candidatura,
        on_delete=models.PROTECT,
        related_name="carta",
        verbose_name="candidatura",
    )
    ano = models.PositiveSmallIntegerField("ano")
    sequencia = models.PositiveIntegerField("número sequencial")
    emitida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cartas_emitidas",
        verbose_name="emitida por",
    )
    emitida_em = models.DateTimeField("emitida em", default=timezone.now)

    class Meta:
        ordering = ["-ano", "-sequencia"]
        verbose_name = "carta de encaminhamento"
        verbose_name_plural = "cartas de encaminhamento"
        constraints = [
            models.UniqueConstraint(fields=["ano", "sequencia"], name="carta_numero_unico")
        ]

    def __str__(self):
        return f"Ofício {self.referencia}"

    @property
    def referencia(self):
        return f"{self.sequencia:03d}/{self.ano}/{config.SIGLA_OFICIO}"

    @property
    def nome_ficheiro(self):
        return f"carta-encaminhamento-{self.sequencia:03d}-{self.ano}.pdf"

    @classmethod
    def emitir(cls, candidatura, utilizador):
        """Devolve (carta, criada). Só emite para candidaturas aprovadas."""
        existente = cls.objects.filter(candidatura=candidatura).first()
        if existente:
            return existente, False

        if candidatura.estado != Candidatura.Estado.APROVADO:
            raise ValidationError(
                "Só é possível emitir a carta de encaminhamento de uma candidatura aprovada."
            )

        with transaction.atomic():
            ano = timezone.localdate().year
            ultima = cls.objects.filter(ano=ano).aggregate(m=Max("sequencia"))["m"] or 0
            carta = cls.objects.create(
                candidatura=candidatura,
                ano=ano,
                sequencia=ultima + 1,
                emitida_por=utilizador,
            )
        return carta, True