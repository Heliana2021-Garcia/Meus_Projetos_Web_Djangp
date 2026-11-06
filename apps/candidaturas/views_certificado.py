from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View

from apps.contas.mixins import TipoRequeridoMixin
from apps.core.pdf_utils import html_para_pdf

from . import servicos_avaliacao as servicos
from .views_avaliacao import INTERVENIENTES, T, _candidatura


class CertificadoView(TipoRequeridoMixin, View):
    tipos_permitidos = INTERVENIENTES + (T.ADMINISTRADOR,)
    http_method_names = ["get"]

    def get(self, request, pk):
        c = _candidatura(pk)
        if servicos.papel_do_utilizador(c, request.user) is None and request.user.tipo != T.ADMINISTRADOR:
            raise Http404
        if c.estagio_estado != "CONCLUIDO":
            messages.error(
                request,
                "O certificado só fica disponível depois de a empresa aprovar a conclusão do estágio.",
            )
            return redirect("candidaturas:avaliacao", pk=c.pk)

        pdf = html_para_pdf("documentos/certificado.html", {
            "c": c,
            "referencia": f"SIGEST-{c.concluida_em:%Y}-{c.pk:05d}",
            "emitido_em": timezone.localdate(),
        })
        resposta = HttpResponse(pdf, content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="certificado-estagio-{c.pk}.pdf"'
        return resposta