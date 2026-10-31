import csv

from django.http import HttpResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.core.pdf_utils import html_para_pdf

from . import filtros_estagios as filtros

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


class ExportarEstagiosCsvView(TipoRequeridoMixin, View):
    tipos_permitidos = GESTAO
    http_method_names = ["get"]

    def get(self, request):
        estados = dict(filtros.ESTADOS)
        resposta = HttpResponse(content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = (
            f'attachment; filename="relatorio_estagios_{timezone.localdate():%Y%m%d}.csv"'
        )
        resposta.write("\ufeff")
        saida = csv.writer(resposta, delimiter=";")
        saida.writerow([
            "Número", "Estudante", "Curso", "Empresa", "Vaga", "Modalidade", "Orientador",
            "Estado", "Início", "Conclusão prevista", "Concluído em", "Nota final",
        ])
        for c in filtros.filtrar(request.GET):
            saida.writerow([
                c.estudante.numero_estudante,
                c.estudante.utilizador.get_full_name() or c.estudante.utilizador.username,
                c.estudante.curso.sigla,
                c.vaga.empresa.nome,
                c.vaga.titulo,
                c.vaga.get_tipo_estagio_display(),
                c.orientador.utilizador.get_full_name() if c.orientador_id else "",
                estados[c.estagio_estado],
                _data(c.data_inicio),
                _data(c.data_fim),
                _data(c.concluida_em),
                c.avaliacao_final if c.estagio_estado == "CONCLUIDO" else "",
            ])
        return resposta


class ExportarEstagiosPdfView(TipoRequeridoMixin, View):
    tipos_permitidos = GESTAO
    http_method_names = ["get"]

    def get(self, request):
        linhas = list(filtros.filtrar(request.GET))
        contagem, media = filtros.totais(linhas)
        pdf = html_para_pdf("relatorios/relatorio_estagios_pdf.html", {
            "linhas": linhas,
            "total": len(linhas),
            "contagem": contagem,
            "media": media,
            "filtros_aplicados": filtros.descrever(request.GET),
            "gerado_em": timezone.localtime(),
            "gerado_por": request.user.get_full_name() or request.user.username,
        })
        resposta = HttpResponse(pdf, content_type="application/pdf")
        resposta["Content-Disposition"] = (
            f'inline; filename="relatorio_estagios_{timezone.localdate():%Y%m%d}.pdf"'
        )
        return resposta