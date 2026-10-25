from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import ModeloBase, Tecnologia


class Curso(ModeloBase):
    nome = models.CharField("nome", max_length=120, unique=True)
    sigla = models.CharField("sigla", max_length=10, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "curso"
        verbose_name_plural = "cursos"

    def __str__(self):
        return self.nome


class PerfilEstudante(ModeloBase):
    ANO_MINIMO_CANDIDATURA = 3
    MEDIA_MINIMA_CANDIDATURA = Decimal("14.00")

    class Estado(models.TextChoices):
        DISPONIVEL = "DISPONIVEL", "Disponível"
        OCUPADO = "OCUPADO", "Ocupado"

    utilizador = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil_estudante",
        limit_choices_to={"tipo": "ESTUDANTE"},
        verbose_name="utilizador",
    )
    numero_estudante = models.CharField("número de estudante", max_length=20, unique=True)
    curso = models.ForeignKey(
        Curso, on_delete=models.PROTECT, related_name="estudantes", verbose_name="curso"
    )
    ano_frequencia = models.PositiveSmallIntegerField(
        "ano de frequência",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    media_geral = models.DecimalField(
        "média geral",
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
    )
    resumo = models.TextField("resumo profissional", blank=True)
    curriculo = models.FileField("currículo (PDF)", upload_to="curriculos/", blank=True)
    tecnologias = models.ManyToManyField(
        Tecnologia, blank=True, related_name="estudantes", verbose_name="tecnologias"
    )
    estado = models.CharField(
        "estado", max_length=12, choices=Estado.choices, default=Estado.DISPONIVEL
    )

    class Meta:
        ordering = ["utilizador__first_name", "utilizador__last_name"]
        verbose_name = "perfil de estudante"
        verbose_name_plural = "perfis de estudantes"

    def __str__(self):
        return f"{self.utilizador} ({self.numero_estudante})"

    @property
    def motivos_inelegibilidade(self):
        motivos = []
        if self.ano_frequencia < self.ANO_MINIMO_CANDIDATURA:
            motivos.append(
                f"É necessário frequentar o {self.ANO_MINIMO_CANDIDATURA}º ano ou superior."
            )
        if self.media_geral < self.MEDIA_MINIMA_CANDIDATURA:
            motivos.append(
                f"A média geral tem de ser pelo menos {self.MEDIA_MINIMA_CANDIDATURA} valores."
            )
        return motivos

    @property
    def elegivel(self):
        return not self.motivos_inelegibilidade

    def marcar_ocupado(self):
        self.estado = self.Estado.OCUPADO
        self.save(update_fields=["estado", "atualizado_em"])

    def marcar_disponivel(self):
        self.estado = self.Estado.DISPONIVEL
        self.save(update_fields=["estado", "atualizado_em"])
