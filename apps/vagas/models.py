from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from apps.core.models import ModeloBase, Tecnologia
from apps.empresas.models import Empresa
from apps.estudantes.models import Curso


class VagaQuerySet(models.QuerySet):
    def publicas(self):
        hoje = timezone.localdate()
        return self.filter(
            estado=Vaga.Estado.ABERTA,
            empresa__nif_validado=True,
        ).filter(Q(data_limite__isnull=True) | Q(data_limite__gte=hoje))

    def para_feed(self):
        """Vagas públicas, com as das empresas parceiras em destaque."""
        return (
            self.publicas()
            .annotate(
                destaque=Case(
                    When(empresa__tipo=Empresa.Tipo.PARCEIRA, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .order_by("-destaque", "-criado_em")
        )


class Vaga(ModeloBase):
    class Modalidade(models.TextChoices):
        PRESENCIAL = "PRESENCIAL", "Presencial"
        REMOTO = "REMOTO", "Remoto"
        HIBRIDO = "HIBRIDO", "Híbrido"

    class Estado(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        ABERTA = "ABERTA", "Aberta"
        ENCERRADA = "ENCERRADA", "Encerrada"

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="vagas", verbose_name="empresa"
    )
    titulo = models.CharField("título", max_length=150)
    descricao = models.TextField("descrição", blank=True)
    requisitos = models.TextField("requisitos", blank=True)
    cursos = models.ManyToManyField(
        Curso,
        blank=True,
        related_name="vagas",
        verbose_name="cursos aceites",
        help_text="Se ficar vazio, aceita estudantes de qualquer curso.",
    )
    tecnologias = models.ManyToManyField(
        Tecnologia, blank=True, related_name="vagas", verbose_name="tecnologias exigidas"
    )
    numero_vagas = models.PositiveSmallIntegerField("número de lugares", default=1)
    localizacao = models.CharField("localização", max_length=120, blank=True)
    modalidade = models.CharField(
        "modalidade", max_length=12, choices=Modalidade.choices, default=Modalidade.PRESENCIAL
    )
    duracao_meses = models.PositiveSmallIntegerField("duração (meses)", default=3)
    data_limite = models.DateField("data limite de candidatura", null=True, blank=True)
    estado = models.CharField(
        "estado", max_length=10, choices=Estado.choices, default=Estado.RASCUNHO
    )

    objects = VagaQuerySet.as_manager()

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "vaga"
        verbose_name_plural = "vagas"

    def __str__(self):
        return f"{self.titulo} — {self.empresa}"

    def clean(self):
        if (
            self.empresa_id
            and self.estado == self.Estado.ABERTA
            and not self.empresa.nif_validado
        ):
            raise ValidationError(
                {"estado": "A vaga só pode ser publicada depois de a administração validar o NIF da empresa."}
            )

    @property
    def expirada(self):
        return self.data_limite is not None and self.data_limite < timezone.localdate()

    @property
    def publica(self):
        return (
            self.estado == self.Estado.ABERTA
            and self.empresa.nif_validado
            and not self.expirada
        )

    @property
    def lugares_ocupados(self):
        return self.candidaturas.filter(estado="APROVADO").count()

    @property
    def tem_lugares(self):
        return self.lugares_ocupados < self.numero_vagas

    def publicar(self):
        anterior = self.estado
        self.estado = self.Estado.ABERTA
        try:
            self.full_clean()
        except ValidationError:
            self.estado = anterior
            raise
        self.save(update_fields=["estado", "atualizado_em"])

    def encerrar(self):
        self.estado = self.Estado.ENCERRADA
        self.save(update_fields=["estado", "atualizado_em"])

    def aceita_curso(self, curso):
        return not self.cursos.exists() or self.cursos.filter(pk=curso.pk).exists()

    def tecnologias_em_falta(self, perfil):
        return self.tecnologias.exclude(
            pk__in=perfil.tecnologias.values_list("pk", flat=True)
        )

    def compatibilidade(self, perfil):
        """Percentagem (0-100) das tecnologias exigidas que o estudante tem."""
        total = self.tecnologias.count()
        if total == 0:
            return 100
        em_falta = self.tecnologias_em_falta(perfil).count()
        return round(100 * (total - em_falta) / total)
