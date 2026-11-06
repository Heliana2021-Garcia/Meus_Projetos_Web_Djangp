from decimal import Decimal

import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
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
    class Registo(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente de validação"
        APROVADO = "APROVADO", "Aprovado"
        DEVOLVIDO = "DEVOLVIDO", "Devolvido para correcção"

    registo_estado = models.CharField(
        "estado do registo", max_length=12, choices=Registo.choices, default=Registo.APROVADO
    )
    registo_motivo = models.TextField("motivo da devolução", blank=True)
    registo_decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="decidido por",
    )
    registo_decidido_em = models.DateTimeField("decidido em", null=True, blank=True)
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
        motivos = []                                #1
        if self.registo_estado != self.Registo.APROVADO: #2
            motivos.append("O seu registo ainda não foi validado pela coordenação.") #3
        if self.ano_frequencia < self.ANO_MINIMO_CANDIDATURA:  #4
            motivos.append(                                     #5
                f"É necessário frequentar o {self.ANO_MINIMO_CANDIDATURA}º ano ou superior."
            )
        if self.media_geral < self.MEDIA_MINIMA_CANDIDATURA:  #6
            motivos.append(                             #7
                f"A média geral tem de ser pelo menos {self.MEDIA_MINIMA_CANDIDATURA} valores."
            )
        return motivos   #8

    @property
    def elegivel(self):
        return not self.motivos_inelegibilidade

    def marcar_ocupado(self):
        self.estado = self.Estado.OCUPADO
        self.save(update_fields=["estado", "atualizado_em"])

    def marcar_disponivel(self):
        self.estado = self.Estado.DISPONIVEL
        self.save(update_fields=["estado", "atualizado_em"])

    TIPOS_OBRIGATORIOS = ("DECLARACAO", "FREQUENCIA")

    @property
    def tem_documentos_obrigatorios(self):
        existentes = set(self.documentos.values_list("tipo", flat=True))
        return set(self.TIPOS_OBRIGATORIOS) <= existentes

    def guardar_documento(self, tipo, ficheiro):
        """Cria o documento ou substitui o anterior, apagando o ficheiro antigo."""
        documento = self.documentos.filter(tipo=tipo).first()
        if documento is None:
            return DocumentoEstudante.objects.create(estudante=self, tipo=tipo, ficheiro=ficheiro)
        documento.ficheiro.delete(save=False)
        documento.ficheiro = ficheiro
        documento.save()
        return documento

    def aprovar_registo(self, utilizador):
        if not self.tem_documentos_obrigatorios:
            raise ValidationError(
                "Faltam documentos obrigatórios (declaração com notas e declaração de frequência)."
            )
        self.registo_estado = self.Registo.APROVADO
        self.registo_motivo = ""
        self.registo_decidido_por = utilizador
        self.registo_decidido_em = timezone.now()
        self.save(update_fields=[
            "registo_estado", "registo_motivo", "registo_decidido_por",
            "registo_decidido_em", "atualizado_em",
        ])

    def devolver_registo(self, utilizador, motivo):
        motivo = (motivo or "").strip()
        if not motivo:
            raise ValidationError("Indique o motivo da devolução.")
        self.registo_estado = self.Registo.DEVOLVIDO
        self.registo_motivo = motivo
        self.registo_decidido_por = utilizador
        self.registo_decidido_em = timezone.now()
        self.save(update_fields=[
            "registo_estado", "registo_motivo", "registo_decidido_por",
            "registo_decidido_em", "atualizado_em",
        ])

    def resubmeter_registo(self):
        self.registo_estado = self.Registo.PENDENTE
        self.save(update_fields=["registo_estado", "atualizado_em"])


def armazenamento_privado():
    """Pasta fora de `media/`, nunca servida directamente: só através da vista com permissões."""
    return FileSystemStorage(location=settings.BASE_DIR / "privado")


def caminho_documento(instancia, nome):
    extensao = os.path.splitext(nome)[1].lower()
    return f"estudantes/{instancia.estudante_id}/{instancia.tipo.lower()}{extensao}"


class DocumentoEstudante(ModeloBase):
    class Tipo(models.TextChoices):
        DECLARACAO = "DECLARACAO", "Declaração com notas"
        FREQUENCIA = "FREQUENCIA", "Declaração de frequência"

    estudante = models.ForeignKey(
        PerfilEstudante, on_delete=models.CASCADE, related_name="documentos",
        verbose_name="estudante",
    )
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices)
    ficheiro = models.FileField(
        "ficheiro", upload_to=caminho_documento, storage=armazenamento_privado
    )

    class Meta:
        verbose_name = "documento do estudante"
        verbose_name_plural = "documentos dos estudantes"
        constraints = [
            models.UniqueConstraint(fields=["estudante", "tipo"], name="documento_unico_por_tipo"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.estudante}"
