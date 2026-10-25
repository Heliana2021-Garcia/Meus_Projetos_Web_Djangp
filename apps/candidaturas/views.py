from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.vagas.mixins import EmpresaRequeridaMixin
from apps.vagas.models import Vaga

from .models import Candidatura

E = Candidatura.Estado

# (estado, rótulo da coluna, próximo estado, rótulo do botão de avanço)
COLUNAS = [
    (E.PENDENTE, "Pendente", E.ENTREVISTA, "Marcar entrevista"),
    (E.ENTREVISTA, "Entrevista", E.PROPOSTA, "Enviar proposta"),
    (E.PROPOSTA, "Proposta", E.APROVADO, "Aprovar"),
    (E.APROVADO, "Aprovado", None, None),
    (E.REJEITADO, "Rejeitado", None, None),
]


def _e_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


# --------------------------------------------------------------- estudante
class MinhasCandidaturasView(TipoRequeridoMixin, ListView):
    tipos_permitidos = (Utilizador.Tipo.ESTUDANTE,)
    template_name = "candidaturas/minhas.html"
    context_object_name = "candidaturas"

    def get_queryset(self):
        return Candidatura.objects.filter(
            estudante__utilizador=self.request.user
        ).select_related("vaga__empresa")


# ----------------------------------------------------------------- empresa
class KanbanVagaView(EmpresaRequeridaMixin, DetailView):
    template_name = "candidaturas/kanban.html"
    context_object_name = "vaga"

    def get_queryset(self):
        return Vaga.objects.filter(empresa=self.empresa)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        vaga = self.object

        candidaturas = list(
            vaga.candidaturas.select_related(
                "estudante__utilizador", "estudante__curso"
            ).prefetch_related("estudante__tecnologias")
        )

        colunas = []
        for estado, rotulo, avanco_estado, avanco_rotulo in COLUNAS:
            itens = [
                {
                    "candidatura": c,
                    "compatibilidade": vaga.compatibilidade(c.estudante),
                }
                for c in candidaturas
                if c.estado == estado
            ]
            colunas.append(
                {
                    "estado": estado,
                    "rotulo": rotulo,
                    "avanco_estado": avanco_estado,
                    "avanco_rotulo": avanco_rotulo,
                    "itens": itens,
                }
            )

        contexto["colunas"] = colunas
        contexto["canceladas"] = [c for c in candidaturas if c.estado == E.CANCELADA]
        contexto["total"] = len(candidaturas)
        return contexto


class MoverCandidaturaView(EmpresaRequeridaMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        candidatura = get_object_or_404(
            Candidatura.objects.select_related("vaga", "estudante__utilizador"),
            pk=pk,
            vaga__empresa=self.empresa,
        )
        novo_estado = request.POST.get("novo_estado", "")
        feedback = request.POST.get("feedback", "")

        erros = []
        if novo_estado not in Candidatura.Estado.values:
            erros.append("Estado inválido.")
        else:
            try:
                candidatura.mover_para(novo_estado, feedback)
            except ValidationError as erro:
                erros.extend(erro.messages)

        if not erros:
            utilizador = candidatura.estudante.utilizador
            messages.success(
                request,
                f"{utilizador.get_full_name() or utilizador.username}"
                f" passou para \"{candidatura.get_estado_display()}\".",
            )

        if _e_ajax(request):
            return JsonResponse(
                {"ok": not erros, "erros": erros}, status=400 if erros else 200
            )

        for mensagem in erros:
            messages.error(request, mensagem)
        return redirect("candidaturas:kanban", pk=candidatura.vaga_id)


class ConcluirEstagioView(EmpresaRequeridaMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        candidatura = get_object_or_404(
            Candidatura.objects.select_related("vaga", "estudante__utilizador"),
            pk=pk,
            vaga__empresa=self.empresa,
        )
        valor = request.POST.get("avaliacao", "").strip().replace(",", ".")

        try:
            nota = Decimal(valor)
            if not nota.is_finite():
                raise InvalidOperation
            nota = nota.quantize(Decimal("0.01"))
        except InvalidOperation:
            messages.error(request, "Indique uma avaliação numérica entre 0 e 20.")
        else:
            try:
                candidatura.concluir_estagio(nota)
            except ValidationError as erro:
                for mensagem in erro.messages:
                    messages.error(request, mensagem)
            else:
                messages.success(
                    request,
                    "Estágio concluído. O estudante voltou a ficar disponível.",
                )
        return redirect("candidaturas:kanban", pk=candidatura.vaga_id)