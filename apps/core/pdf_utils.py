from io import BytesIO

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def caminho_logo():
    """Caminho do logótipo do INSTIC para incluir nos PDF (ou None)."""
    caminho = finders.find("img/logo_instic.png")
    if isinstance(caminho, (list, tuple)):
        caminho = caminho[0] if caminho else None
    return str(caminho).replace("\\", "/") if caminho else None


def html_para_pdf(template, contexto):
    contexto = {**contexto, "logo": caminho_logo()}
    html = render_to_string(template, contexto)
    saida = BytesIO()
    resultado = pisa.CreatePDF(html, dest=saida, encoding="utf-8", link_callback=lambda uri, rel: uri)
    if resultado.err:
        raise RuntimeError("Não foi possível gerar o PDF.")
    return saida.getvalue()