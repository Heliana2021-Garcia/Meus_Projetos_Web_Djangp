import csv
from datetime import date

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from apps.candidaturas.models import Candidatura
from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.empresas.models import Empresa
from apps.estudantes.models import PerfilEstudante

from . import servicos


class PainelAdminView(TipoRequeridoMixin, TemplateView):
    template_name = "relatorios/painel.html"
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["empresas_pendentes"] = Empresa.objects.filter(
            nif_validado=False
        ).select_related("utilizador")
        contexto["aprovadas"] = (
            Candidatura.objects.filter(estado=Candidatura.Estado.APROVADO)
            .select_related(
                "estudante__utilizador", "estudante__curso", "vaga__empresa", "carta"
            )
            .order_by("-atualizado_em")
        )
        contexto["total_estudantes"] = PerfilEstudante.objects.count()
        contexto["total_empresas"] = Empresa.objects.count()
        return contexto


class ValidarNifView(TipoRequeridoMixin, View):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR,)
    http_method_names = ["post"]

    def post(self, request, pk):
        empresa = get_object_or_404(Empresa, pk=pk)
        empresa.validar_nif()
        messages.success(request, f"NIF da empresa {empresa.nome} validado.")
        return redirect("relatorios:painel")


class DashboardView(TipoRequeridoMixin, TemplateView):
    template_name = "relatorios/dashboard.html"
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["ind"] = servicos.indicadores_gerais()
        contexto["por_curso"] = servicos.resumo_por_curso()
        contexto["funil"] = servicos.funil_candidaturas()
        contexto["top_empresas"] = servicos.empresas_com_mais_estagiarios()
        return contexto


def _seguro(valor):
    """Evita que o Excel interprete texto como fórmula."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def _numero(valor):
    return "" if valor is None else str(valor).replace(".", ",")


class ExportarColocacoesView(TipoRequeridoMixin, View):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR,)

    def get(self, request):
        resposta = HttpResponse(content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = (
            f'attachment; filename="colocacoes-{date.today():%Y-%m-%d}.csv"'
        )
        resposta.write("\ufeff")  # para o Excel reconhecer os acentos

        escritor = csv.writer(resposta, delimiter=";")
        escritor.writerow(
            [
                "Número de estudante", "Nome", "Curso", "Ano", "Média geral",
                "Empresa", "Tipo de empresa", "Vaga", "Estado",
                "Avaliação final", "Estágio concluído em", "Carta de encaminhamento",
            ]
        )

        candidaturas = (
            Candidatura.objects.filter(estado=Candidatura.Estado.APROVADO)
            .select_related(
                "estudante__utilizador", "estudante__curso", "vaga__empresa", "carta"
            )
            .order_by("estudante__curso__nome", "estudante__numero_estudante")
        )
        for c in candidaturas:
            e = c.estudante
            carta = getattr(c, "carta", None)
            escritor.writerow(
                [
                    _seguro(e.numero_estudante),
                    _seguro(e.utilizador.get_full_name() or e.utilizador.username),
                    _seguro(e.curso.nome),
                    e.ano_frequencia,
                    _numero(e.media_geral),
                    _seguro(c.vaga.empresa.nome),
                    c.vaga.empresa.get_tipo_display(),
                    _seguro(c.vaga.titulo),
                    "Concluído" if c.concluida_em else "Em curso",
                    _numero(c.avaliacao_final),
                    c.concluida_em.strftime("%d/%m/%Y") if c.concluida_em else "",
                    carta.referencia if carta else "",
                ]
            )
        return resposta