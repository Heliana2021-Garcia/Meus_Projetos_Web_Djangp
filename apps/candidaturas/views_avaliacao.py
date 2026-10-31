from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.vagas.mixins import EstudanteRequeridoMixin

from . import servicos_avaliacao as servicos
from .forms_avaliacao import AvaliacaoForm
from .models import Avaliacao, Candidatura
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
        existentes = {a.papel: a for a in c.avaliacoes.all()}
        linhas = []
        for chave, peso in servicos.pesos().items():
            visivel = concluido or papel != Avaliacao.Papel.ESTUDANTE or chave == Avaliacao.Papel.ESTUDANTE
            linhas.append({
                "rotulo": Avaliacao.Papel(chave).label,
                "peso": peso,
                "avaliacao": existentes.get(chave) if visivel else None,
                "reservada": (not visivel) and chave in existentes,
                "minha": chave == papel,
            })
        pode_concluir = papel == Avaliacao.Papel.COORDENADOR and em_curso
        contexto.update(
            c=c,
            papel=papel,
            linhas=linhas,
            pode_avaliar=bool(papel) and em_curso,
            ja_avaliou=papel in existentes,
            nota_final=c.avaliacao_final if concluido else None,
            nota_provisoria=(
                servicos.nota_final(c) if (not concluido and papel != Avaliacao.Papel.ESTUDANTE) else None
            ),
            pode_concluir=pode_concluir,
            impedimentos=servicos.impedimentos_conclusao(c) if pode_concluir else [],
        )
        return contexto


class AvaliarView(TipoRequeridoMixin, FormView):
    tipos_permitidos = INTERVENIENTES
    template_name = "candidaturas/avaliar.html"
    form_class = AvaliacaoForm

    @cached_property
    def candidatura(self):
        return _candidatura(self.kwargs["pk"])

    @cached_property
    def papel(self):
        papel = servicos.papel_do_utilizador(self.candidatura, self.request.user)
        if papel is None:
            raise Http404
        return papel

    @cached_property
    def instancia(self):
        return self.candidatura.avaliacoes.filter(papel=self.papel).first()

    def _bloqueado(self):
        if self.candidatura.estagio_estado != "EM_CURSO":
            messages.error(self.request, "Só é possível avaliar com o estágio em curso.")
            return redirect("candidaturas:avaliacao", pk=self.candidatura.pk)
        return None

    def get(self, request, *args, **kwargs):
        self.papel  # valida a participação (404 se não participa)
        return self._bloqueado() or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.papel
        return self._bloqueado() or super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.instancia
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            c=self.candidatura,
            papel_rotulo=Avaliacao.Papel(self.papel).label,
            peso=servicos.pesos().get(self.papel, 0),
        )
        return contexto

    def form_valid(self, form):
        nova = self.instancia is None
        avaliacao = form.save(commit=False)
        avaliacao.candidatura = self.candidatura
        avaliacao.papel = self.papel
        avaliacao.avaliador = self.request.user
        avaliacao.save()
        if nova:
            servicos.apos_nova_avaliacao(self.candidatura)
        messages.success(self.request, "Avaliação guardada.")
        return redirect("candidaturas:avaliacao", pk=self.candidatura.pk)


class MinhaAvaliacaoView(EstudanteRequeridoMixin, View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        estagio = estagio_do_estudante(self.perfil)
        if estagio is None:
            messages.info(request, "Ainda não tem nenhum estágio para avaliar.")
            return redirect("candidaturas:estagio")
        return redirect("candidaturas:avaliacao", pk=estagio.pk)


class ValidarConclusaoView(TipoRequeridoMixin, View):
    tipos_permitidos = (T.COORDENADOR,)
    http_method_names = ["post"]

    def post(self, request, pk):
        c = _candidatura(pk)
        try:
            servicos.concluir(c, request.user)
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            messages.success(request, f"Estágio concluído. Nota final: {c.avaliacao_final}.")
        return redirect("candidaturas:avaliacao", pk=c.pk)