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
        TESTE = "TESTE", "Teste psicotécnico"
        CURRICULO = "CURRICULO", "Análise do currículo"
        ENTREVISTA = "ENTREVISTA", "Entrevista presencial"
        PROPOSTA = "PROPOSTA", "Decisão final"
        APROVADO = "APROVADO", "Aprovado"
        REJEITADO = "REJEITADO", "Rejeitado"
        CANCELADA = "CANCELADA", "Cancelada"

    ESTADOS_ATIVOS = ["PENDENTE", "TESTE", "CURRICULO", "ENTREVISTA", "PROPOSTA"]
    # Ordem possível do processo. As fases opcionais só existem se a vaga as activar.
    ORDEM = list(Vaga.ESTADOS_PROCESSO)
    ROTULOS_ETAPA = {
        "PENDENTE": "Candidatura recebida",
        "TESTE": "Teste psicotécnico",
        "CURRICULO": "Análise do currículo",
        "ENTREVISTA": "Entrevista presencial",
        "PROPOSTA": "Decisão final",
        "APROVADO": "Aprovado",
    }

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
    orientador = models.ForeignKey(
        "empresas.Orientador", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="estagios", verbose_name="orientador empresarial",
    )
    inicio_confirmado_empresa = models.DateTimeField("início confirmado pela empresa", null=True, blank=True)
    inicio_confirmado_estudante = models.DateTimeField("início confirmado pelo estudante", null=True, blank=True)
    interrompido_em = models.DateTimeField("interrompido em", null=True, blank=True)
    motivo_interrupcao = models.TextField("motivo da interrupção", blank=True)
    interrompido_por = models.ForeignKey(
        "contas.Utilizador", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="interrompido por",
    )
    concluida_em = models.DateTimeField("concluída em", null=True, blank=True)
    efectivado = models.BooleanField("efectivado pela empresa", null=True, blank=True)
    efectivado_em = models.DateTimeField("efectivação registada em", null=True, blank=True)

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
        return not self.transicoes_permitidas

    @property
    def transicoes_permitidas(self):
        if self.estado not in self.ESTADOS_ATIVOS:
            return []
        atual = self.ORDEM.index(self.estado)
        proximo = next((e for e in self.sequencia() if self.ORDEM.index(e) > atual), None)
        return [proximo, self.Estado.REJEITADO] if proximo else []

    @property
    def _nome_estudante(self):
        utilizador = self.estudante.utilizador
        return utilizador.get_full_name() or utilizador.username

    # ---------------------------------------------------------------- Kanban
    def mover_para(self, novo_estado, feedback=""):
        if novo_estado not in self.transicoes_permitidas:
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
        if self.interrompido_em:
            raise ValidationError("Este estágio foi interrompido e não pode ser concluído.")

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
            self.Estado.CURRICULO: (
                "Análise do currículo",
                f"A empresa {empresa} está a analisar o seu currículo para a vaga \"{vaga}\".",
            ),
            self.Estado.TESTE: (
                "Teste psicotécnico",
                f"A empresa {empresa} convocou-o(a) para o teste psicotécnico da vaga \"{vaga}\". "
                "Só avança para a entrevista se passar no teste.",
            ),
            self.Estado.ENTREVISTA: (
                "Entrevista",
                f"A empresa {empresa} passou a sua candidatura a \"{vaga}\" para a fase de entrevista.",
            ),
            self.Estado.PROPOSTA: (
                "Decisão final",
                f"A sua candidatura à vaga \"{vaga}\" chegou à decisão final na empresa {empresa}.",
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

    def sequencia(self):
        """Estados do processo desta candidatura, segundo as fases activas da vaga."""
        return self.vaga.estados_do_processo()

    @property
    def etapas(self):
        """Etapas para mostrar ao estudante: feita, atual ou futura."""
        if self.estado not in self.ESTADOS_ATIVOS and self.estado != self.Estado.APROVADO:
            return []
        atual = self.ORDEM.index(self.estado)
        etapas = []
        for estado in self.sequencia():
            indice = self.ORDEM.index(estado)
            if indice < atual or self.estado == self.Estado.APROVADO:
                situacao = "feita"
            elif indice == atual:
                situacao = "atual"
            else:
                situacao = "futura"
            etapas.append({"rotulo": self.ROTULOS_ETAPA[estado], "situacao": situacao})
        return etapas

    # ----------------------------------------------------------------- estágio
    @property
    def estagio_estado(self):
        if self.estado != self.Estado.APROVADO:
            return ""
        if self.interrompido_em:
            return "INTERROMPIDO"
        if self.concluida_em:
            return "CONCLUIDO"
        if self.inicio_confirmado_empresa and self.inicio_confirmado_estudante:
            return "EM_CURSO"
        return "POR_INICIAR"

    @property
    def estagio_aberto(self):
        return self.estagio_estado in ("POR_INICIAR", "EM_CURSO")

    @staticmethod
    def _somar_meses(data, meses):
        import calendar

        mes = data.month - 1 + meses
        ano = data.year + mes // 12
        mes = mes % 12 + 1
        dia = min(data.day, calendar.monthrange(ano, mes)[1])
        return data.replace(year=ano, month=mes, day=dia)

    def atribuir_orientador(self, orientador):
        if not self.estagio_aberto:
            raise ValidationError("Só é possível atribuir orientador a um estágio por iniciar ou em curso.")
        if orientador.empresa_id != self.vaga.empresa_id:
            raise ValidationError("O orientador tem de pertencer à empresa de acolhimento.")
        if not orientador.utilizador.is_active:
            raise ValidationError("Este orientador está inactivo.")
        if self.orientador_id != orientador.pk and not orientador.pode_receber_estagiario:
            raise ValidationError(
                f"Este orientador já tem {orientador.limite_estagios} estágios activos (limite atingido)."
            )
        self.orientador = orientador
        self.save(update_fields=["orientador", "atualizado_em"])
        notificar(
            orientador.utilizador,
            "Novo estagiário",
            f"Foi-lhe atribuído o estágio de {self._nome_estudante} na vaga \"{self.vaga.titulo}\".",
            reverse("empresas:painel_orientador"),
        )
        notificar(
            self.estudante.utilizador,
            "Orientador atribuído",
            f"A empresa {self.vaga.empresa.nome} atribuiu o orientador "
            f"{orientador.utilizador.get_full_name() or orientador.utilizador.username}. "
            "Confirme o início do estágio.",
            reverse("candidaturas:estagio"),
        )

    def confirmar_inicio(self, utilizador):
        estado = self.estagio_estado
        if estado == "EM_CURSO":
            raise ValidationError("Este estágio já está em curso.")
        if estado != "POR_INICIAR":
            raise ValidationError("Este estágio não pode ser iniciado.")
        if self.orientador_id is None:
            raise ValidationError("A empresa tem de atribuir um orientador antes de confirmar o início.")

        agora = timezone.now()
        campos = []
        if utilizador.pk == self.vaga.empresa.utilizador_id:
            if self.inicio_confirmado_empresa:
                raise ValidationError("A empresa já confirmou o início.")
            self.inicio_confirmado_empresa = agora
            campos.append("inicio_confirmado_empresa")
            outra_parte = self.estudante.utilizador
            url_outra = reverse("candidaturas:estagio")
        elif utilizador.pk == self.estudante.utilizador_id:
            if self.inicio_confirmado_estudante:
                raise ValidationError("Já confirmou o início do estágio.")
            self.inicio_confirmado_estudante = agora
            campos.append("inicio_confirmado_estudante")
            outra_parte = self.vaga.empresa.utilizador
            url_outra = reverse("candidaturas:estagios")
        else:
            raise ValidationError("Não tem permissão para confirmar este início.")

        iniciou = bool(self.inicio_confirmado_empresa and self.inicio_confirmado_estudante)
        if iniciou:
            self.data_inicio = self.data_inicio or timezone.localdate()
            self.data_fim = self._somar_meses(self.data_inicio, self.vaga.duracao_meses)
            campos += ["data_inicio", "data_fim"]
        self.save(update_fields=campos + ["atualizado_em"])

        if iniciou:
            texto = (
                f"O estágio de {self._nome_estudante} em \"{self.vaga.titulo}\" começou "
                f"em {self.data_inicio:%d/%m/%Y}, com conclusão prevista em {self.data_fim:%d/%m/%Y}."
            )
            for destino, url in (
                (self.estudante.utilizador, reverse("candidaturas:estagio")),
                (self.vaga.empresa.utilizador, reverse("candidaturas:estagios")),
                (self.orientador.utilizador, reverse("empresas:painel_orientador")),
            ):
                notificar(destino, "Estágio iniciado", texto, url)
        else:
            notificar(
                outra_parte,
                "Confirmação de início",
                f"Falta a sua confirmação para iniciar o estágio de {self._nome_estudante} "
                f"na vaga \"{self.vaga.titulo}\".",
                url_outra,
            )

    def interromper(self, utilizador, motivo):
        if not self.estagio_aberto:
            raise ValidationError("Só é possível interromper um estágio por iniciar ou em curso.")
        motivo = (motivo or "").strip()
        if not motivo:
            raise ValidationError("Indique o motivo da interrupção.")

        with transaction.atomic():
            self.interrompido_em = timezone.now()
            self.motivo_interrupcao = motivo
            self.interrompido_por = utilizador
            self.save(update_fields=[
                "interrompido_em", "motivo_interrupcao", "interrompido_por", "atualizado_em",
            ])
            self.estudante.marcar_disponivel()

        destinos = [
            (self.estudante.utilizador, reverse("candidaturas:estagio")),
            (self.vaga.empresa.utilizador, reverse("candidaturas:estagios")),
        ]
        if self.orientador_id:
            destinos.append((self.orientador.utilizador, reverse("empresas:painel_orientador")))
        for destino, url in destinos:
            if destino.pk != utilizador.pk:
                notificar(
                    destino,
                    "Estágio interrompido",
                    f"O estágio de {self._nome_estudante} em \"{self.vaga.titulo}\" foi interrompido. "
                    f"Motivo: {motivo}",
                    url,
                )

    @property
    def acompanhamento_por_validar(self):
        return (
            self.registos.filter(estado="SUBMETIDO").count()
            + self.relatorios.filter(estado="SUBMETIDO").count()
        )


class Acompanhamento(models.Model):
    """Base comum: item submetido pelo estudante e validado pelo orientador."""

    class Estado(models.TextChoices):
        SUBMETIDO = "SUBMETIDO", "Por validar"
        VALIDADO = "VALIDADO", "Validado"
        CORRECAO = "CORRECAO", "Correcção pedida"

    estado = models.CharField("estado", max_length=10, choices=Estado.choices, default=Estado.SUBMETIDO)
    comentario_orientador = models.TextField("comentário do orientador", blank=True)
    validado_por = models.ForeignKey(
        "contas.Utilizador", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="decidido por",
    )
    validado_em = models.DateTimeField("decidido em", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def editavel(self):
        return self.estado != self.Estado.VALIDADO

    def avisar_orientador(self):
        orientador = self.candidatura.orientador
        if orientador:
            notificar(
                orientador.utilizador,
                "Acompanhamento por validar",
                f"{self.candidatura._nome_estudante} submeteu: {self.descricao_curta}.",
                reverse("candidaturas:acompanhar", args=[self.candidatura_id]),
            )

    def decidir(self, utilizador, validar, comentario=""):
        orientador = self.candidatura.orientador
        if orientador is None or orientador.utilizador_id != utilizador.pk:
            raise ValidationError("Só o orientador atribuído pode decidir.")
        if self.estado != self.Estado.SUBMETIDO:
            raise ValidationError("Este item não está a aguardar validação.")
        comentario = (comentario or "").strip()
        if not validar and not comentario:
            raise ValidationError("Indique o que deve ser corrigido.")

        self.estado = self.Estado.VALIDADO if validar else self.Estado.CORRECAO
        self.comentario_orientador = comentario
        self.validado_por = utilizador
        self.validado_em = timezone.now()
        self.save()

        resultado = "validado" if validar else f"correcção pedida: {comentario}"
        notificar(
            self.candidatura.estudante.utilizador,
            "Decisão do orientador",
            f"{self.descricao_curta.capitalize()} — {resultado}.",
            self.url_estudante,
        )


class RegistoDiario(Acompanhamento):
    candidatura = models.ForeignKey(Candidatura, on_delete=models.CASCADE, related_name="registos")
    data = models.DateField("data")
    descricao = models.TextField("actividades realizadas")
    competencias = models.TextField("conhecimentos e competências", blank=True)
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        ordering = ["-data"]
        verbose_name = "registo do diário"
        verbose_name_plural = "registos do diário"
        constraints = [
            models.UniqueConstraint(fields=["candidatura", "data"], name="registo_unico_por_dia"),
        ]

    def __str__(self):
        return f"{self.candidatura} · {self.data:%d/%m/%Y}"

    @property
    def descricao_curta(self):
        return f"registo do diário de {self.data:%d/%m/%Y}"

    @property
    def url_estudante(self):
        return reverse("candidaturas:diario")


class RelatorioEstagio(Acompanhamento):
    class Tipo(models.TextChoices):
        INTERCALAR = "INTERCALAR", "Relatório intercalar"
        FINAL = "FINAL", "Relatório final"

    candidatura = models.ForeignKey(Candidatura, on_delete=models.CASCADE, related_name="relatorios")
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices)
    titulo = models.CharField("título", max_length=200)
    conteudo = models.TextField("conteúdo")

    class Meta:
        ordering = ["tipo"]
        verbose_name = "relatório de estágio"
        verbose_name_plural = "relatórios de estágio"
        constraints = [
            models.UniqueConstraint(fields=["candidatura", "tipo"], name="relatorio_unico_por_tipo"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.candidatura}"

    @property
    def descricao_curta(self):
        return self.get_tipo_display().lower()

    @property
    def url_estudante(self):
        return reverse("candidaturas:relatorios")

from decimal import ROUND_HALF_UP, Decimal  # noqa: E402

from django.core.validators import MaxValueValidator, MinValueValidator  # noqa: E402


def pesos_avaliacao():
    from django.conf import settings

    return getattr(
        settings, "PESOS_AVALIACAO",
        {"EMPRESA": 30, "ORIENTADOR": 30, "ESTUDANTE": 10, "COORDENADOR": 30},
    )


def _nota(rotulo):
    return models.DecimalField(
        rotulo, max_digits=4, decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("20"))],
    )


class Avaliacao(models.Model):
    """Avaliação do estágio feita por um dos intervenientes (uma por papel)."""

    class Papel(models.TextChoices):
        EMPRESA = "EMPRESA", "Empresa"
        ORIENTADOR = "ORIENTADOR", "Orientador empresarial"
        ESTUDANTE = "ESTUDANTE", "Estudante"
        COORDENADOR = "COORDENADOR", "Coordenação institucional"

    CRITERIOS = (
        ("objectivos", "Cumprimento dos objectivos"),
        ("qualidade", "Qualidade das actividades"),
        ("responsabilidade", "Responsabilidade"),
        ("assiduidade", "Assiduidade"),
        ("competencias", "Evolução das competências"),
    )

    candidatura = models.ForeignKey(Candidatura, on_delete=models.CASCADE, related_name="avaliacoes")
    papel = models.CharField("avaliador", max_length=12, choices=Papel.choices)
    avaliador = models.ForeignKey(
        "contas.Utilizador", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="registada por",
    )
    objectivos = _nota("Cumprimento dos objectivos")
    qualidade = _nota("Qualidade das actividades")
    responsabilidade = _nota("Responsabilidade")
    assiduidade = _nota("Assiduidade")
    competencias = _nota("Evolução das competências")
    nota = models.DecimalField("nota", max_digits=5, decimal_places=2, default=0, editable=False)
    comentario = models.TextField("comentário", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["papel"]
        verbose_name = "avaliação"
        verbose_name_plural = "avaliações"
        constraints = [
            models.UniqueConstraint(fields=["candidatura", "papel"], name="avaliacao_unica_por_papel"),
        ]

    def __str__(self):
        return f"{self.get_papel_display()} · {self.candidatura} · {self.nota}"

    @property
    def peso(self):
        return pesos_avaliacao().get(self.papel, 0)

    def save(self, *args, **kwargs):
        valores = [getattr(self, nome) for nome, _ in self.CRITERIOS]
        media = sum((Decimal(v) for v in valores), Decimal("0")) / len(valores)
        self.nota = media.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)
