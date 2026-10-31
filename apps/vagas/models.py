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
        EM_ANALISE = "EM_ANALISE", "Em análise"
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

    motivo_devolucao = models.TextField("motivo da devolução", blank=True)

    class Tipo(models.TextChoices):
        CURRICULAR = "CURRICULAR", "Curricular"
        PROFISSIONAL = "PROFISSIONAL", "Profissional"

    area = models.CharField("área de estágio", max_length=100, blank=True)
    tipo_estagio = models.CharField(
        "tipo de estágio", max_length=12, choices=Tipo.choices, default=Tipo.CURRICULAR
    )
    documentos_exigidos = models.TextField(
        "documentos obrigatórios",
        blank=True,
        help_text="Um por linha. Ex.: currículo, certificado de habilitações.",
    )
    fase_teste = models.BooleanField(
        "teste psicotécnico", default=True,
        help_text="Fase de selecção. A decisão final existe sempre, no fim do processo.",
    )
    fase_curriculo = models.BooleanField(
        "análise do currículo", default=False, help_text="Fase de selecção."
    )
    fase_entrevista = models.BooleanField(
        "entrevista presencial", default=True, help_text="Fase de selecção."
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
            and self.estado in (self.Estado.ABERTA, self.Estado.EM_ANALISE)
            and not self.empresa.nif_validado
        ):
            raise ValidationError(
                {"estado": "A vaga só pode ser submetida depois de o INSTIC aprovar a parceria (validação do NIF da empresa)."}
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

    def submeter(self):
        """A empresa envia a vaga para o INSTIC aprovar."""
        anterior = self.estado
        self.estado = self.Estado.EM_ANALISE
        try:
            self.full_clean()
        except ValidationError:
            self.estado = anterior
            raise
        self.motivo_devolucao = ""
        self.save(update_fields=["estado", "motivo_devolucao", "atualizado_em"])

    def devolver(self, motivo):
        """O INSTIC devolve a vaga à empresa, com o motivo."""
        if not motivo.strip():
            raise ValidationError("Indique o motivo da devolução.")
        self.estado = self.Estado.RASCUNHO
        self.motivo_devolucao = motivo.strip()
        self.save(update_fields=["estado", "motivo_devolucao", "atualizado_em"])

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

    ESTADOS_PROCESSO = ("PENDENTE", "TESTE", "CURRICULO", "ENTREVISTA", "PROPOSTA", "APROVADO")
    FASES = (
        ("TESTE", "fase_teste", "Teste psicotécnico"),
        ("CURRICULO", "fase_curriculo", "Análise do currículo"),
        ("ENTREVISTA", "fase_entrevista", "Entrevista presencial"),
    )

    def fases_activas(self):
        """Fases opcionais que esta vaga activou."""
        return [estado for estado, campo, _ in self.FASES if getattr(self, campo)]

    def estados_do_processo(self):
        """Sequência de estados de uma candidatura a esta vaga, pela ordem do processo."""
        opcionais = set(self.fases_activas())
        fixos = {"PENDENTE", "PROPOSTA", "APROVADO"}
        return [e for e in self.ESTADOS_PROCESSO if e in fixos or e in opcionais]

    @property
    def rotulos_processo(self):
        fases = [rotulo for _, campo, rotulo in self.FASES if getattr(self, campo)]
        return fases + ["Decisão final"]
