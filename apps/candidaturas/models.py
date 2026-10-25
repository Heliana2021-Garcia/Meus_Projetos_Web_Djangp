from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import ModeloBase
from apps.core.notificacoes import notificar
from apps.estudantes.models import PerfilEstudante
from apps.vagas.models import Vaga


class Candidatura(ModeloBase):
    class Estado(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        ENTREVISTA = "ENTREVISTA", "Entrevista"
        PROPOSTA = "PROPOSTA", "Proposta"
        APROVADO = "APROVADO", "Aprovado"
        REJEITADO = "REJEITADO", "Rejeitado"
        CANCELADA = "CANCELADA", "Cancelada"

    # Transições permitidas no Kanban de selecção
    TRANSICOES = {
        "PENDENTE": ["ENTREVISTA", "REJEITADO"],
        "ENTREVISTA": ["PROPOSTA", "REJEITADO"],
        "PROPOSTA": ["APROVADO", "REJEITADO"],
        "APROVADO": [],
        "REJEITADO": [],
        "CANCELADA": [],
    }
    ESTADOS_ATIVOS = ["PENDENTE", "ENTREVISTA", "PROPOSTA"]

    estudante = models.ForeignKey(
        PerfilEstudante,
        on_delete=models.PROTECT,
        related_name="candidaturas",
        verbose_name="estudante",
    )
    vaga = models.ForeignKey(
        Vaga, on_delete=models.PROTECT, related_name="candidaturas", verbose_name="vaga"
    )
    estado = models.CharField(
        "estado", max_length=12, choices=Estado.choices, default=Estado.PENDENTE
    )
    mensagem = models.TextField("carta de motivação", blank=True)
    feedback = models.TextField("feedback da empresa", blank=True)
    data_inicio = models.DateField("início do estágio", null=True, blank=True)
    data_fim = models.DateField("fim do estágio", null=True, blank=True)
    avaliacao_final = models.DecimalField(
        "avaliação final (0-20)",
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
    )
    concluida_em = models.DateTimeField("concluída em", null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "candidatura"
        verbose_name_plural = "candidaturas"
        constraints = [
            models.UniqueConstraint(
                fields=["estudante", "vaga"], name="candidatura_unica_por_vaga"
            )
        ]

    def __str__(self):
        return f"{self.estudante} → {self.vaga} [{self.get_estado_display()}]"

    # ------------------------------------------------------------ validação
    def clean(self):
        if self.estado == self.Estado.REJEITADO and not self.feedback.strip():
            raise ValidationError(
                {"feedback": "O feedback é obrigatório ao rejeitar uma candidatura."}
            )

        if not self.estudante_id or not self.vaga_id:
            return

        if self._state.adding:
            erros = []
            if not self.vaga.publica:
                erros.append("Esta vaga não está disponível para candidaturas.")
            if not self.vaga.aceita_curso(self.estudante.curso):
                erros.append("Esta vaga não aceita estudantes do seu curso.")
            if self.estudante.estado == PerfilEstudante.Estado.OCUPADO:
                erros.append("O estudante está ocupado com um estágio em curso.")
            erros.extend(self.estudante.motivos_inelegibilidade)
            if erros:
                raise ValidationError(erros)

    def save(self, *args, **kwargs):
        nova = self._state.adding
        if nova:
            self.full_clean()
        super().save(*args, **kwargs)
        if nova:
            self._notificar_nova()

    # ----------------------------------------------------------- propriedades
    @property
    def e_final(self):
        return not self.TRANSICOES[self.estado]

    @property
    def transicoes_permitidas(self):
        return self.TRANSICOES[self.estado]

    @property
    def _nome_estudante(self):
        utilizador = self.estudante.utilizador
        return utilizador.get_full_name() or utilizador.username

    # ---------------------------------------------------------------- Kanban
    def mover_para(self, novo_estado, feedback=""):
        if novo_estado not in self.TRANSICOES.get(self.estado, []):
            raise ValidationError(
                f"Não é possível passar de {self.get_estado_display()} "
                f"para {self.Estado(novo_estado).label}."
            )

        if novo_estado == self.Estado.REJEITADO:
            if not feedback.strip():
                raise ValidationError("O feedback é obrigatório ao rejeitar uma candidatura.")
            self.feedback = feedback.strip()

        if novo_estado == self.Estado.APROVADO:
            if self.estudante.estado == PerfilEstudante.Estado.OCUPADO:
                raise ValidationError("O estudante já está ocupado com outro estágio.")
            if not self.vaga.tem_lugares:
                raise ValidationError("A vaga já não tem lugares disponíveis.")

        canceladas = []
        with transaction.atomic():
            self.estado = novo_estado
            self.save(update_fields=["estado", "feedback", "atualizado_em"])
            if novo_estado == self.Estado.APROVADO:
                self.estudante.marcar_ocupado()
                canceladas = self._cancelar_outras_candidaturas()

        self._notificar_mudanca(bool(canceladas))
        for outra in canceladas:
            outra._notificar_cancelamento()

    def _cancelar_outras_candidaturas(self):
        """Cancela as outras candidaturas ativas do estudante (foi aprovado aqui)."""
        outras = list(
            Candidatura.objects.filter(
                estudante=self.estudante, estado__in=self.ESTADOS_ATIVOS
            )
            .exclude(pk=self.pk)
            .select_related("vaga__empresa__utilizador", "estudante__utilizador")
        )
        if outras:
            Candidatura.objects.filter(pk__in=[c.pk for c in outras]).update(
                estado=self.Estado.CANCELADA, atualizado_em=timezone.now()
            )
            for outra in outras:
                outra.estado = self.Estado.CANCELADA
        return outras

    def concluir_estagio(self, avaliacao):
        if self.estado != self.Estado.APROVADO:
            raise ValidationError("Só é possível concluir o estágio de uma candidatura aprovada.")
        if self.concluida_em:
            raise ValidationError("Este estágio já foi concluído.")

        nota = Decimal(str(avaliacao))
        if not Decimal("0") <= nota <= Decimal("20"):
            raise ValidationError("A avaliação final tem de estar entre 0 e 20.")

        with transaction.atomic():
            self.avaliacao_final = nota
            self.concluida_em = timezone.now()
            self.save(update_fields=["avaliacao_final", "concluida_em", "atualizado_em"])
            self.estudante.marcar_disponivel()

        notificar(
            self.estudante.utilizador,
            "Estágio concluído",
            f"A empresa {self.vaga.empresa.nome} concluiu o seu estágio "
            f"\"{self.vaga.titulo}\" com a avaliação final de {nota:.2f}/20.",
            reverse("candidaturas:minhas"),
        )

    # ------------------------------------------------------------ notificações
    def _notificar_nova(self):
        notificar(
            self.vaga.empresa.utilizador,
            "Nova candidatura",
            f"{self._nome_estudante} candidatou-se à vaga \"{self.vaga.titulo}\".",
            reverse("candidaturas:kanban", args=[self.vaga_id]),
        )

    def _notificar_mudanca(self, houve_cancelamentos):
        empresa = self.vaga.empresa.nome
        vaga = self.vaga.titulo
        mensagens = {
            self.Estado.ENTREVISTA: (
                "Entrevista",
                f"A empresa {empresa} passou a sua candidatura a \"{vaga}\" para a fase de entrevista.",
            ),
            self.Estado.PROPOSTA: (
                "Recebeu uma proposta",
                f"A empresa {empresa} enviou-lhe uma proposta para \"{vaga}\".",
            ),
            self.Estado.APROVADO: (
                "Candidatura aprovada",
                f"Parabéns! A empresa {empresa} aprovou a sua candidatura a \"{vaga}\". "
                "A administração do INSTIC irá emitir a carta de encaminhamento.",
            ),
            self.Estado.REJEITADO: (
                "Candidatura rejeitada",
                f"A empresa {empresa} rejeitou a sua candidatura a \"{vaga}\".",
            ),
        }
        titulo, texto = mensagens[self.estado]
        if self.estado == self.Estado.APROVADO and houve_cancelamentos:
            texto += " As suas outras candidaturas ativas foram canceladas automaticamente."
        if self.estado == self.Estado.REJEITADO and self.feedback:
            texto += f" Feedback: {self.feedback}"
        notificar(
            self.estudante.utilizador, titulo, texto, reverse("candidaturas:minhas")
        )

    def _notificar_cancelamento(self):
        notificar(
            self.vaga.empresa.utilizador,
            "Candidatura cancelada",
            f"{self._nome_estudante} foi aprovado(a) noutra vaga. A candidatura a "
            f"\"{self.vaga.titulo}\" foi cancelada automaticamente.",
            reverse("candidaturas:kanban", args=[self.vaga_id]),
        )