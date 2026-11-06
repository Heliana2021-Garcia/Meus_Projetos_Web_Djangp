from io import BytesIO

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.staticfiles import finders
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.generic import TemplateView
from xhtml2pdf import pisa

from . import relatorio_gestao as rg


def _recurso(uri, rel):
    base = settings.STATIC_URL or "/static/"
    if uri.startswith(base):
        return finders.find(uri[len(base):]) or uri
    return uri


def _url_estagios():
    for nome in ("relatorios:relatorio_estagios", "relatorio_estagios"):
        try:
            return reverse(nome)
        except NoReverseMatch:
            continue
    return ""


class RelatorioGestaoView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "relatorios/relatorio_gestao.html"

    def test_func(self):
        return self.request.user.e_gestao

    def get(self, request, *args, **kwargs):
        chave = request.GET.get("entidade")
        if chave not in rg.ENTIDADES:
            chave = "candidaturas"
        relatorio = rg.gerar(chave, request.GET)
        agora = timezone.localtime()
        formato = request.GET.get("formato")

        if formato == "csv":
            resposta = HttpResponse(rg.para_csv(relatorio, request.user, agora), content_type="text/csv; charset=utf-8")
            resposta["Content-Disposition"] = (
                f'attachment; filename="sigest_{chave}_{agora:%Y%m%d}.csv"')
            return resposta

        if formato == "pdf":
            html = render_to_string("relatorios/relatorio_gestao_pdf.html", {
                "rel": relatorio, "gerado_em": agora, "utilizador": request.user,
                "meta": rg.metadados(relatorio, request.user, agora)})
            buffer = BytesIO()
            resultado = pisa.CreatePDF(html, dest=buffer, encoding="utf-8", link_callback=_recurso)
            if resultado.err:
                return HttpResponse("Não foi possível gerar o PDF.", status=500)
            resposta = HttpResponse(buffer.getvalue(), content_type="application/pdf")
            resposta["Content-Disposition"] = (
                f'attachment; filename="sigest_{chave}_{agora:%Y%m%d}.pdf"')
            return resposta

        consulta = request.GET.copy()
        for chave_extra in ("pagina", "formato"):
            consulta.pop(chave_extra, None)
        consulta["entidade"] = chave
        pagina = Paginator(relatorio["linhas"], 25).get_page(request.GET.get("pagina"))
        contexto = {
            "rel": relatorio,
            "chave": chave,
            "pagina": pagina,
            "consulta": consulta.urlencode(),
            "entidades": [(k, v["titulo"]) for k, v in rg.ENTIDADES.items()],
            "url_estagios": _url_estagios(),
        }
        return self.render_to_response(contexto)