from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.empresas.models import Orientador
from apps.vagas.mixins import EmpresaRequeridaMixin, EstudanteRequeridoMixin
from apps.vagas.models import Vaga

from .models import Candidatura

E = Candidatura.Estado

ROTULOS_COLUNA = {
    "PENDENTE": "Pendente",
    "TESTE": "Teste psicotécnico",
    "CURRICULO": "Análise do currículo",
    "ENTREVISTA": "Entrevista presencial",
    "PROPOSTA": "Decisão final",
    "APROVADO": "Aprovado",
    "REJEITADO": "Rejeitado",
}
# Rótulo do botão, conforme o estado para onde o cartão vai
ROTULOS_AVANCO = {
    "TESTE": "Convocar para o teste",
    "CURRICULO": "Passar à análise do currículo",
    "ENTREVISTA": "Marcar entrevista",
    "PROPOSTA": "Passar à decisão final",
    "APROVADO": "Aprovar",
}


def _e_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


# --------------------------------------------------------------- estudante
class MinhasCandidaturasView(TipoRequeridoMixin, ListView):
    tipos_permitidos = (Utilizador.Tipo.ESTUDANTE,)
    template_name = "candidaturas/minhas.html"
    context_object_name = "candidaturas"

    def get_queryset(self):
        consulta = Candidatura.objects.filter(
            estudante__utilizador=self.request.user
        ).select_related("vaga__empresa__utilizador")
        q = self.request.GET.get("q", "").strip()
        if q:
            consulta = consulta.filter(Q(vaga__titulo__icontains=q) | Q(vaga__empresa__nome__icontains=q))
        estado = self.request.GET.get("estado", "").strip()
        if estado in Candidatura.Estado.values:
            consulta = consulta.filter(estado=estado)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "").strip()
        contexto["estado"] = self.request.GET.get("estado", "").strip()
        contexto["estados"] = Candidatura.Estado.choices
        contexto["tem_filtros"] = bool(contexto["q"] or contexto["estado"])
        contexto["total_geral"] = Candidatura.objects.filter(
            estudante__utilizador=self.request.user
        ).count()
        return contexto


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

        ordem = Candidatura.ORDEM
        processo = vaga.estados_do_processo()
        presentes = {c.estado for c in candidaturas}
        # Mostra as fases da vaga e, por segurança, qualquer fase onde ainda haja candidatos
        estados = [e for e in ordem if e in processo or e in presentes]

        colunas = []
        for estado in estados + ["REJEITADO"]:
            avanco = None
            if estado in ordem and estado != "APROVADO":
                indice = ordem.index(estado)
                avanco = next((e for e in processo if ordem.index(e) > indice), None)
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
                    "rotulo": ROTULOS_COLUNA[estado],
                    "avanco_estado": avanco,
                    "avanco_rotulo": ROTULOS_AVANCO.get(avanco, ""),
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


# ------------------------------------------------------------------ estágio
class EstagiosEmpresaView(EmpresaRequeridaMixin, ListView):
    template_name = "candidaturas/estagios_empresa.html"
    context_object_name = "estagios"

    def get_queryset(self):
        consulta = (
            Candidatura.objects.filter(estado=E.APROVADO, vaga__empresa=self.empresa)
            .select_related("vaga", "estudante__utilizador", "estudante__curso", "orientador__utilizador")
            .order_by("-atualizado_em")
        )
        q = self.request.GET.get("q", "").strip()
        if q:
            consulta = consulta.filter(
                Q(estudante__utilizador__first_name__icontains=q)
                | Q(estudante__utilizador__last_name__icontains=q)
                | Q(estudante__numero_estudante__icontains=q)
                | Q(vaga__titulo__icontains=q)
            )
        orientador = self.request.GET.get("orientador", "").strip()
        if orientador == "sem":
            consulta = consulta.filter(orientador__isnull=True)
        elif orientador == "com":
            consulta = consulta.filter(orientador__isnull=False)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "").strip()
        contexto["orientador_filtro"] = self.request.GET.get("orientador", "").strip()
        contexto["opcoes_orientador"] = [("sem", "Sem orientador"), ("com", "Com orientador")]
        contexto["tem_filtros"] = bool(contexto["q"] or contexto["orientador_filtro"])
        contexto["orientadores"] = Orientador.objects.filter(
            empresa=self.empresa, utilizador__is_active=True
        ).select_related("utilizador")
        return contexto


class AtribuirOrientadorView(EmpresaRequeridaMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        candidatura = get_object_or_404(
            Candidatura.objects.select_related("vaga__empresa", "estudante__utilizador"),
            pk=pk, estado=E.APROVADO, vaga__empresa=self.empresa,
        )
        try:
            identificador = int(request.POST.get("orientador", ""))
        except ValueError:
            identificador = None
        orientador = (
            Orientador.objects.select_related("utilizador", "empresa")
            .filter(pk=identificador, empresa=self.empresa)
            .first()
            if identificador
            else None
        )
        if orientador is None:
            messages.error(request, "Seleccione um orientador da sua empresa.")
        else:
            try:
                candidatura.atribuir_orientador(orientador)
            except ValidationError as erro:
                for mensagem in erro.messages:
                    messages.error(request, mensagem)
            else:
                messages.success(request, "Orientador atribuído.")
        return redirect("candidaturas:estagios")


class ConfirmarInicioView(TipoRequeridoMixin, View):
    tipos_permitidos = (Utilizador.Tipo.EMPRESA, Utilizador.Tipo.ESTUDANTE)
    http_method_names = ["post"]

    def post(self, request, pk):
        base = Candidatura.objects.select_related(
            "vaga__empresa__utilizador", "estudante__utilizador", "orientador__utilizador"
        ).filter(estado=E.APROVADO)
        if request.user.tipo == Utilizador.Tipo.EMPRESA:
            candidatura = get_object_or_404(base, pk=pk, vaga__empresa__utilizador=request.user)
            destino = "candidaturas:estagios"
        else:
            candidatura = get_object_or_404(base, pk=pk, estudante__utilizador=request.user)
            destino = "candidaturas:estagio"
        try:
            candidatura.confirmar_inicio(request.user)
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            messages.success(request, "Confirmação registada.")
        return redirect(destino)


class InterromperEstagioView(TipoRequeridoMixin, View):
    tipos_permitidos = (
        Utilizador.Tipo.EMPRESA, Utilizador.Tipo.COORDENADOR, Utilizador.Tipo.ADMINISTRADOR,
    )
    http_method_names = ["post"]

    def post(self, request, pk):
        base = Candidatura.objects.select_related(
            "vaga__empresa__utilizador", "estudante__utilizador", "orientador__utilizador"
        ).filter(estado=E.APROVADO)
        if request.user.tipo == Utilizador.Tipo.EMPRESA:
            candidatura = get_object_or_404(base, pk=pk, vaga__empresa__utilizador=request.user)
            destino = "candidaturas:estagios"
        else:
            candidatura = get_object_or_404(base, pk=pk)
            destino = "relatorios:estagios"
        try:
            candidatura.interromper(request.user, request.POST.get("motivo", ""))
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            messages.success(request, "Estágio interrompido. O estudante voltou a ficar disponível.")
        return redirect(destino)


class EstagioEstudanteView(EstudanteRequeridoMixin, TemplateView):
    template_name = "candidaturas/estagio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        lista = list(
            Candidatura.objects.filter(estudante=self.perfil, estado=E.APROVADO)
            .select_related("vaga__empresa", "orientador__utilizador")
            .order_by("-atualizado_em")
        )
        atual = next((c for c in lista if c.estagio_aberto), None)
        contexto["estagio"] = atual
        contexto["historico"] = [c for c in lista if c is not atual]
        return contexto
