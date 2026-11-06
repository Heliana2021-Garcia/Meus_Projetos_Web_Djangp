from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.vagas.mixins import EstudanteRequeridoMixin

from . import servicos_avaliacao as servicos
from .forms_avaliacao import AvaliacaoMensalForm
from .models import Candidatura
from .views_estagio import estagio_do_estudante

E = Candidatura.Estado
T = Utilizador.Tipo
INTERVENIENTES = (T.EMPRESA, T.ORIENTADOR, T.ESTUDANTE, T.COORDENADOR)


def _candidatura(pk):
    return get_object_or_404(
        Candidatura.objects.select_related(
            "vaga__empresa", "estudante__utilizador", "estudante__curso", "orientador__utilizador"
        ),
        pk=pk, estado=E.APROVADO,
    )


class AvaliacaoEstagioView(TipoRequeridoMixin, TemplateView):
    """Notas do diario, nota final, avaliacoes mensais (so empresa/estudante) e conclusao (so empresa)."""

    tipos_permitidos = INTERVENIENTES + (T.ADMINISTRADOR,)
    template_name = "candidaturas/avaliacao.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        c = _candidatura(self.kwargs["pk"])
        utilizador = self.request.user
        papel = servicos.papel_do_utilizador(c, utilizador)
        if papel is None and utilizador.tipo != T.ADMINISTRADOR:
            raise Http404

        concluido = c.estagio_estado == "CONCLUIDO"
        em_curso = c.estagio_estado == "EM_CURSO"
        mostrar_mensais = papel in (servicos.EMPRESA, servicos.ESTUDANTE) and c.data_inicio is not None
        pode_concluir = papel == servicos.EMPRESA and em_curso
        contexto.update(
            c=c,
            papel=papel,
            registos=c.registos.order_by("data"),
            nota_final=c.avaliacao_final if concluido else None,
            nota_provisoria=None if concluido else servicos.nota_final(c),
            mostrar_mensais=mostrar_mensais,
            mensais=servicos.estado_mensal(c) if mostrar_mensais else [],
            proximo_mes=servicos.proximo_mes(c) if (papel == servicos.ESTUDANTE and em_curso) else None,
            pode_concluir=pode_concluir,
            impedimentos=servicos.impedimentos_conclusao(c) if pode_concluir else [],
        )
        return contexto


class AvaliarOrientadorView(EstudanteRequeridoMixin, FormView):
    """O estudante avalia o orientador (uma vez por mes de estagio). A avaliacao vai para a empresa."""

    template_name = "candidaturas/avaliar_orientador.html"
    form_class = AvaliacaoMensalForm

    @cached_property
    def estagio(self):
        return estagio_do_estudante(self.perfil)

    @cached_property
    def mes(self):
        estagio = self.estagio
        if not estagio or estagio.estagio_estado != "EM_CURSO":
            return None
        return servicos.proximo_mes(estagio)

    def _sem_mes(self):
        if self.mes is None:
            messages.info(
                self.request, "Não há nenhuma avaliação mensal disponível neste momento."
            )
            return redirect("candidaturas:minha_avaliacao")
        return None

    def get(self, request, *args, **kwargs):
        return self._sem_mes() or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._sem_mes() or super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            c=self.estagio, mes=self.mes, total=servicos.total_avaliacoes_mensais(self.estagio)
        )
        return contexto

    def form_valid(self, form):
        c = self.estagio
        avaliacao = form.save(commit=False)
        avaliacao.candidatura = c
        avaliacao.mes = self.mes
        avaliacao.orientador = c.orientador
        try:
            with transaction.atomic():
                avaliacao.save()
        except IntegrityError:
            messages.error(self.request, "Esta avaliação já foi enviada.")
            return redirect("candidaturas:avaliacao", pk=c.pk)
        servicos.apos_avaliacao_mensal(c, avaliacao)
        messages.success(self.request, "Avaliação enviada à empresa.")
        return redirect("candidaturas:avaliacao", pk=c.pk)


class MinhaAvaliacaoView(EstudanteRequeridoMixin, View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        estagio = estagio_do_estudante(self.perfil)
        if estagio is None:
            messages.info(request, "Ainda não tem nenhum estágio para avaliar.")
            return redirect("candidaturas:estagio")
        return redirect("candidaturas:avaliacao", pk=estagio.pk)


class ValidarConclusaoView(TipoRequeridoMixin, View):
    """Aprovacao da conclusao: so a empresa de acolhimento."""

    tipos_permitidos = (T.EMPRESA,)
    http_method_names = ["post"]

    def post(self, request, pk):
        c = _candidatura(pk)
        if c.vaga.empresa.utilizador_id != request.user.pk:
            raise Http404
        try:
            servicos.concluir(c, request.user)
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            messages.success(request, f"Estágio concluído. Nota final: {c.avaliacao_final}.")
        return redirect("candidaturas:avaliacao", pk=c.pk)
