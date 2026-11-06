from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import FormView, TemplateView, UpdateView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.vagas.mixins import EstudanteRequeridoMixin

from .forms_estagio import RegistoDiarioForm, RelatorioForm
from .models import Candidatura, RegistoDiario, RelatorioEstagio

E = Candidatura.Estado


def estagio_do_estudante(perfil):
    """O estágio aberto do estudante; se não houver, o mais recente."""
    lista = list(
        Candidatura.objects.filter(estudante=perfil, estado=E.APROVADO)
        .select_related("vaga__empresa", "orientador__utilizador")
        .order_by("-atualizado_em")
    )
    return next((c for c in lista if c.estagio_aberto), lista[0] if lista else None)


class DiarioView(EstudanteRequeridoMixin, TemplateView):
    template_name = "candidaturas/diario.html"

    @cached_property
    def estagio(self):
        return estagio_do_estudante(self.perfil)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        estagio = self.estagio
        em_curso = bool(estagio and estagio.estagio_estado == "EM_CURSO")
        contexto.update(
            estagio=estagio,
            em_curso=em_curso,
            registos=estagio.registos.all() if estagio else [],
        )
        if em_curso and "form" not in contexto:
            contexto["form"] = RegistoDiarioForm(
                candidatura=estagio, initial={"data": timezone.localdate()}
            )
        return contexto

    def post(self, request, *args, **kwargs):
        estagio = self.estagio
        if not estagio or estagio.estagio_estado != "EM_CURSO":
            messages.error(request, "O diário só pode ser preenchido com o estágio em curso.")
            return redirect("candidaturas:diario")
        form = RegistoDiarioForm(request.POST, candidatura=estagio)
        if form.is_valid():
            form.save()
            messages.success(request, "Registo guardado e enviado ao orientador.")
            return redirect("candidaturas:diario")
        return self.render_to_response(self.get_context_data(form=form))


class EditarRegistoView(EstudanteRequeridoMixin, UpdateView):
    form_class = RegistoDiarioForm
    template_name = "candidaturas/registo_form.html"

    def get_queryset(self):
        return (
            RegistoDiario.objects.filter(candidatura__estudante=self.perfil)
            .exclude(estado=RegistoDiario.Estado.VALIDADO)
            .select_related("candidatura")
        )

    def get_object(self, queryset=None):
        registo = super().get_object(queryset)
        if registo.candidatura.estagio_estado != "EM_CURSO":
            raise Http404
        return registo

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["candidatura"] = self.object.candidatura
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Registo corrigido e enviado de novo ao orientador.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("candidaturas:diario")


class RelatoriosEstudanteView(EstudanteRequeridoMixin, TemplateView):
    template_name = "candidaturas/relatorios.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        estagio = estagio_do_estudante(self.perfil)
        existentes = {r.tipo: r for r in estagio.relatorios.all()} if estagio else {}
        contexto["estagio"] = estagio
        contexto["em_curso"] = bool(estagio and estagio.estagio_estado == "EM_CURSO")
        contexto["itens"] = [
            {"slug": valor.lower(), "rotulo": rotulo, "obj": existentes.get(valor)}
            for valor, rotulo in RelatorioEstagio.Tipo.choices
        ]
        return contexto


class RelatorioEstudanteView(EstudanteRequeridoMixin, FormView):
    template_name = "candidaturas/relatorio_form.html"
    form_class = RelatorioForm

    @cached_property
    def estagio(self):
        return estagio_do_estudante(self.perfil)

    @cached_property
    def tipo(self):
        valor = self.kwargs["tipo"].upper()
        if valor not in RelatorioEstagio.Tipo.values:
            raise Http404
        return valor

    @cached_property
    def instancia(self):
        return self.estagio.relatorios.filter(tipo=self.tipo).first() if self.estagio else None

    def _impedimento(self):
        if not self.estagio or self.estagio.estagio_estado != "EM_CURSO":
            return "Os relatórios só podem ser escritos com o estágio em curso."
        if self.instancia and not self.instancia.editavel:
            return "Este relatório já foi validado e não pode ser alterado."
        return None

    def get(self, request, *args, **kwargs):
        erro = self._impedimento()
        if erro:
            messages.error(request, erro)
            return redirect("candidaturas:relatorios")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        erro = self._impedimento()
        if erro:
            messages.error(request, erro)
            return redirect("candidaturas:relatorios")
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(candidatura=self.estagio, tipo=self.tipo, instance=self.instancia)
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["rotulo"] = RelatorioEstagio.Tipo(self.tipo).label
        contexto["relatorio"] = self.instancia
        return contexto

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Relatório guardado e enviado ao orientador.")
        return redirect("candidaturas:relatorios")


class AcompanharEstagioView(TipoRequeridoMixin, TemplateView):
    tipos_permitidos = (
        Utilizador.Tipo.ORIENTADOR, Utilizador.Tipo.EMPRESA,
        Utilizador.Tipo.COORDENADOR, Utilizador.Tipo.ADMINISTRADOR,
    )
    template_name = "candidaturas/acompanhar.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        candidatura = get_object_or_404(
            Candidatura.objects.select_related(
                "vaga__empresa", "estudante__utilizador", "estudante__curso", "orientador__utilizador"
            ),
            pk=self.kwargs["pk"], estado=E.APROVADO,
        )
        utilizador = self.request.user
        eh_orientador = utilizador.tipo == Utilizador.Tipo.ORIENTADOR
        if eh_orientador:
            permitido = bool(
                candidatura.orientador_id and candidatura.orientador.utilizador_id == utilizador.pk
            )
        elif utilizador.tipo == Utilizador.Tipo.EMPRESA:
            permitido = candidatura.vaga.empresa.utilizador_id == utilizador.pk
        else:
            permitido = True
        if not permitido:
            raise Http404
        contexto.update(
            c=candidatura,
            registos=candidatura.registos.all(),
            relatorios=candidatura.relatorios.all(),
            pode_decidir=eh_orientador,
        )
        return contexto


class DecidirView(TipoRequeridoMixin, View):
    tipos_permitidos = (Utilizador.Tipo.ORIENTADOR,)
    http_method_names = ["post"]
    MODELOS = {"registo": RegistoDiario, "relatorio": RelatorioEstagio}

    def post(self, request, tipo, pk):
        modelo = self.MODELOS.get(tipo)
        if modelo is None:
            raise Http404
        item = get_object_or_404(
            modelo.objects.select_related(
                "candidatura__orientador__utilizador", "candidatura__estudante__utilizador"
            ),
            pk=pk, candidatura__orientador__utilizador=request.user,
        )
        validar = request.POST.get("acao") == "validar"
        try:
            item.decidir(request.user, validar, request.POST.get("comentario", ""), request.POST.get("nota"))
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            messages.success(request, "Decisão registada.")
            from . import servicos_avaliacao

            servicos_avaliacao.avisar_se_pronto(item.candidatura)
        return redirect("candidaturas:acompanhar", pk=item.candidatura_id)
from apps.core.notificacoes import notificar  # noqa: E402
from apps.vagas.mixins import EmpresaRequeridaMixin  # noqa: E402


class RegistarEfectivacaoView(EmpresaRequeridaMixin, View):
    """A empresa indica, uma única vez, se o estagiário foi efectivado."""

    http_method_names = ["post"]

    def post(self, request, pk):
        c = get_object_or_404(
            Candidatura.objects.select_related("estudante__utilizador", "vaga__empresa"),
            pk=pk, estado=E.APROVADO, vaga__empresa=self.empresa,
        )
        resultado = request.POST.get("resultado")
        if c.estagio_estado != "CONCLUIDO":
            messages.error(request, "A efectivação só pode ser registada depois da conclusão do estágio.")
        elif c.efectivado is not None:
            messages.error(request, "A efectivação já foi registada.")
        elif resultado not in ("sim", "nao"):
            messages.error(request, "Indique se o estagiário foi efectivado.")
        else:
            c.efectivado = resultado == "sim"
            c.efectivado_em = timezone.now()
            c.save(update_fields=["efectivado", "efectivado_em", "atualizado_em"])
            if c.efectivado:
                notificar(
                    c.estudante.utilizador,
                    "Efectivação",
                    f"A empresa {c.vaga.empresa.nome} indicou que foi efectivado após o estágio.",
                    reverse("candidaturas:avaliacao", args=[c.pk]),
                )
            messages.success(request, "Efectivação registada.")
        return redirect("candidaturas:estagios")
