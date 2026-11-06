import csv

from django.http import HttpResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.core.pdf_utils import html_para_pdf

from . import filtros_estagios as filtros
from . import modelo_registo as modelo

GESTAO = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)


def _data(valor):
    return valor.strftime("%d/%m/%Y") if valor else ""


class RelatorioEstagiosView(TipoRequeridoMixin, TemplateView):
    tipos_permitidos = GESTAO
    template_name = "relatorios/relatorio_estagios.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        linhas = list(filtros.filtrar(self.request.GET))
        contagem, media = filtros.totais(linhas)
        contexto.update(
            linhas=linhas,
            total=len(linhas),
            contagem=contagem,
            media=media,
            efectivados=sum(1 for c in linhas if c.efectivado),
            cursos=filtros.cursos(),
            tipos=filtros.tipos(),
            estados=filtros.ESTADOS,
            filtros=self.request.GET,
            query=self.request.GET.urlencode(),
        )
        return contexto


def _registos(linhas):
    estados = dict(filtros.ESTADOS)
    registos = []
    for c in linhas:
        e = c.estudante
        registos.append((
            e.utilizador.get_full_name() or e.utilizador.username,
            e.curso.sigla,
            modelo.telefone(e),
            e.utilizador.email,
            modelo.observacoes(
                "N.º " + str(e.numero_estudante),
                c.vaga.empresa.nome,
                c.vaga.titulo,
                c.vaga.get_tipo_estagio_display(),
                ("Orientador: " + c.orientador.utilizador.get_full_name()) if c.orientador_id else "",
                estados[c.estagio_estado],
                ("Início " + _data(c.data_inicio)) if c.data_inicio else "",
                ("Conclusão prevista " + _data(c.data_fim)) if c.data_fim else "",
                ("Concluído em " + _data(c.concluida_em)) if c.concluida_em else "",
                ("Nota final " + str(c.avaliacao_final)) if c.estagio_estado == "CONCLUIDO" and c.avaliacao_final is not None else "",
            ),
        ))
    return registos


class ExportarEstagiosCsvView(TipoRequeridoMixin, View):
    tipos_permitidos = GESTAO
    http_method_names = ["get"]

    def get(self, request):
        registos = _registos(filtros.filtrar(request.GET))
        conteudo = modelo.csv_registo(
            "Estágios", registos, request.user,
            filtros=filtros.descrever(request.GET) or ())
        resposta = HttpResponse(conteudo, content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = (
            f'attachment; filename="relatorio_estagios_{timezone.localdate():%Y%m%d}.csv"'
        )
        return resposta


class ExportarEstagiosPdfView(TipoRequeridoMixin, View):
    tipos_permitidos = GESTAO
    http_method_names = ["get"]

    def get(self, request):
        registos = _registos(filtros.filtrar(request.GET))
        descricao = filtros.descrever(request.GET) or ()
        if isinstance(descricao, str):
            descricao = [descricao]
        pdf = html_para_pdf("relatorios/relatorio_estagios_pdf.html", {
            "rel": {"titulo": "Estágios", "registos": registos, "total": len(registos)},
            "meta": modelo.metadados(request.user, filtros=descricao),
        })
        resposta = HttpResponse(pdf, content_type="application/pdf")
        resposta["Content-Disposition"] = (
            f'inline; filename="relatorio_estagios_{timezone.localdate():%Y%m%d}.pdf"'
        )
        return resposta
