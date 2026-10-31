from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import ModeloBase


class Empresa(ModeloBase):
    class Tipo(models.TextChoices):
        PARCEIRA = "PARCEIRA", "Parceira Institucional"
        GERAL = "GERAL", "Empresa Geral"

    utilizador = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="empresa",
        limit_choices_to={"tipo": "EMPRESA"},
        verbose_name="utilizador",
    )
    nome = models.CharField("nome", max_length=150)
    nif = models.CharField("NIF", max_length=20, unique=True)
    tipo = models.CharField("tipo", max_length=10, choices=Tipo.choices, default=Tipo.GERAL)
    sector = models.CharField("sector de actividade", max_length=100, blank=True)
    telefone = models.CharField("telefone", max_length=30, blank=True)
    endereco = models.CharField("endereço", max_length=255, blank=True)
    nif_validado = models.BooleanField("NIF validado", default=False)
    validado_em = models.DateTimeField("validado em", null=True, blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "empresa"
        verbose_name_plural = "empresas"

    def __str__(self):
        return self.nome

    @property
    def e_parceira(self):
        return self.tipo == self.Tipo.PARCEIRA

    @property
    def pode_publicar_vagas(self):
        return self.nif_validado

    def validar_nif(self):
        self.nif_validado = True
        self.validado_em = timezone.now()
        self.save(update_fields=["nif_validado", "validado_em", "atualizado_em"])

class Orientador(ModeloBase):
    """Funcionário da empresa de acolhimento que acompanha o estagiário."""

    utilizador = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orientador",
        limit_choices_to={"tipo": "ORIENTADOR"},
        verbose_name="utilizador",
    )
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="orientadores", verbose_name="empresa"
    )
    cargo = models.CharField("cargo / função", max_length=100, blank=True)

    class Meta:
        ordering = ["utilizador__first_name", "utilizador__last_name"]
        verbose_name = "orientador empresarial"
        verbose_name_plural = "orientadores empresariais"

    def __str__(self):
        return f"{self.utilizador} ({self.empresa})"

    @property
    def limite_estagios(self):
        return getattr(settings, "MAX_ESTAGIOS_POR_ORIENTADOR", 3)

    def estagios_activos(self):
        return self.estagios.filter(
            estado="APROVADO", concluida_em__isnull=True, interrompido_em__isnull=True
        )

    @property
    def total_activos(self):
        return self.estagios_activos().count()

    @property
    def pode_receber_estagiario(self):
        return self.utilizador.is_active and self.total_activos < self.limite_estagios
