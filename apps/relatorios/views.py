import csv

from . import modelo_registo as modelo
from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.candidaturas.models import Candidatura
from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.empresas.models import Empresa
from apps.core.notificacoes import notificar
from apps.estudantes.models import Curso, PerfilEstudante
from apps.vagas.models import Vaga

from . import servicos


class PainelAdminView(TipoRequeridoMixin, TemplateView):
    template_name = "relatorios/painel.html"
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)

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
        contexto["registos_pendentes"] = PerfilEstudante.objects.filter(
            registo_estado=PerfilEstudante.Registo.PENDENTE
        ).count()
        contexto["vagas_em_analise_total"] = Vaga.objects.filter(
            estado=Vaga.Estado.EM_ANALISE
        ).count()
        contexto["total_empresas"] = Empresa.objects.count()
        return contexto


class ValidarNifView(TipoRequeridoMixin, View):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)
    http_method_names = ["post"]

    def post(self, request, pk):
        empresa = get_object_or_404(Empresa, pk=pk)
        empresa.validar_nif()
        notificar(
            empresa.utilizador,
            "Parceria aprovada",
            "O INSTIC aprovou o seu pedido de parceria. Já pode submeter vagas de estágio.",
            reverse("vagas:minhas"),
        )
        messages.success(request, f"Parceria da empresa {empresa.nome} aprovada.")
        return redirect("relatorios:painel")


class DashboardView(TipoRequeridoMixin, TemplateView):
    template_name = "relatorios/dashboard.html"
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)

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
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)

    def get(self, request):
        candidaturas = (
            Candidatura.objects.filter(estado=Candidatura.Estado.APROVADO)
            .select_related("estudante__utilizador", "estudante__curso", "vaga__empresa")
            .order_by("estudante__curso__nome", "estudante__numero_estudante")
        )
        registos = []
        for c in candidaturas:
            e = c.estudante
            carta = getattr(c, "carta", None)
            registos.append((
                e.utilizador.get_full_name() or e.utilizador.username,
                e.curso.nome,
                modelo.telefone(e),
                e.utilizador.email,
                modelo.observacoes(
                    "N.º " + str(e.numero_estudante),
                    str(e.ano_frequencia) + ".º ano",
                    "Média " + str(e.media_geral),
                    c.vaga.empresa.nome,
                    c.vaga.empresa.get_tipo_display(),
                    c.vaga.titulo,
                    "Concluído" if c.concluida_em else "Em curso",
                    ("Avaliação final " + str(c.avaliacao_final)) if c.avaliacao_final is not None else "",
                    ("Concluído em " + c.concluida_em.strftime("%d/%m/%Y")) if c.concluida_em else "",
                    "Carta de encaminhamento emitida" if carta else "",
                ),
            ))
        conteudo = modelo.csv_registo("Colocações", registos, request.user,
                                      periodo="Estágios com candidatura aprovada")
        resposta = HttpResponse(conteudo, content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = (
            f'attachment; filename="colocacoes-{date.today():%Y-%m-%d}.csv"'
        )
        return resposta

class VagasEmAnaliseView(TipoRequeridoMixin, ListView):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)
    template_name = "relatorios/vagas_analise.html"
    context_object_name = "vagas"

    def get_queryset(self):
        return (
            Vaga.objects.filter(estado=Vaga.Estado.EM_ANALISE)
            .select_related("empresa")
            .prefetch_related("cursos", "tecnologias")
            .order_by("criado_em")
        )


class AprovarVagaView(TipoRequeridoMixin, View):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)
    http_method_names = ["post"]

    def post(self, request, pk):
        vaga = get_object_or_404(Vaga, pk=pk, estado=Vaga.Estado.EM_ANALISE)
        try:
            vaga.publicar()
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            notificar(
                vaga.empresa.utilizador,
                "Vaga aprovada",
                f"O INSTIC aprovou a vaga \"{vaga.titulo}\". Já está visível para os estudantes.",
                reverse("vagas:minhas"),
            )
            messages.success(request, f"Vaga \"{vaga.titulo}\" publicada.")
        return redirect("relatorios:vagas_analise")


class DevolverVagaView(TipoRequeridoMixin, View):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)
    http_method_names = ["post"]

    def post(self, request, pk):
        vaga = get_object_or_404(Vaga, pk=pk, estado=Vaga.Estado.EM_ANALISE)
        try:
            vaga.devolver(request.POST.get("motivo", ""))
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            notificar(
                vaga.empresa.utilizador,
                "Vaga devolvida",
                f"O INSTIC devolveu a vaga \"{vaga.titulo}\": {vaga.motivo_devolucao}",
                reverse("vagas:minhas"),
            )
            messages.success(request, f"Vaga \"{vaga.titulo}\" devolvida à empresa.")
        return redirect("relatorios:vagas_analise")

class EstudantesPendentesView(TipoRequeridoMixin, ListView):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)
    template_name = "relatorios/estudantes_pendentes.html"
    context_object_name = "perfis"

    def get_queryset(self):
        consulta = (
            PerfilEstudante.objects.filter(registo_estado=PerfilEstudante.Registo.PENDENTE)
            .select_related("utilizador", "curso")
            .prefetch_related("documentos")
            .order_by("criado_em")
        )
        q = self.request.GET.get("q", "").strip()
        if q:
            consulta = consulta.filter(
                Q(utilizador__first_name__icontains=q)
                | Q(utilizador__last_name__icontains=q)
                | Q(utilizador__email__icontains=q)
                | Q(numero_estudante__icontains=q)
            )
        curso = self.request.GET.get("curso", "").strip()
        if curso.isdigit():
            consulta = consulta.filter(curso_id=int(curso))
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "").strip()
        contexto["curso_filtro"] = self.request.GET.get("curso", "").strip()
        contexto["cursos"] = Curso.objects.values_list("pk", "nome")
        contexto["tem_filtros"] = bool(contexto["q"] or contexto["curso_filtro"])
        return contexto


class AprovarEstudanteView(TipoRequeridoMixin, View):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)
    http_method_names = ["post"]

    def post(self, request, pk):
        perfil = get_object_or_404(PerfilEstudante, pk=pk, registo_estado=PerfilEstudante.Registo.PENDENTE)
        try:
            perfil.aprovar_registo(request.user)
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            notificar(
                perfil.utilizador,
                "Registo aprovado",
                "A coordenação validou o seu registo. Já pode consultar as oportunidades"
                + (" e candidatar-se." if perfil.elegivel else "."),
                reverse("vagas:feed"),
            )
            messages.success(request, f"Registo de {perfil.utilizador} aprovado.")
        return redirect("relatorios:estudantes_pendentes")


class DevolverEstudanteView(TipoRequeridoMixin, View):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)
    http_method_names = ["post"]

    def post(self, request, pk):
        perfil = get_object_or_404(PerfilEstudante, pk=pk, registo_estado=PerfilEstudante.Registo.PENDENTE)
        try:
            perfil.devolver_registo(request.user, request.POST.get("motivo", ""))
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            notificar(
                perfil.utilizador,
                "Registo devolvido para correcção",
                f"A coordenação devolveu o seu registo: {perfil.registo_motivo}",
                reverse("contas:editar_perfil") + "#documentos",
            )
            messages.success(request, f"Registo de {perfil.utilizador} devolvido ao estudante.")
        return redirect("relatorios:estudantes_pendentes")

class EstagiosGestaoView(TipoRequeridoMixin, ListView):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)
    template_name = "relatorios/estagios.html"
    context_object_name = "estagios"
    paginate_by = 20

    def get_queryset(self):
        return (
            Candidatura.objects.filter(estado=Candidatura.Estado.APROVADO)
            .select_related(
                "vaga__empresa", "estudante__utilizador", "estudante__curso", "orientador__utilizador"
            )
            .order_by("-atualizado_em")
        )
