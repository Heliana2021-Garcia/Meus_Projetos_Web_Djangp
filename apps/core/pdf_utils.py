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


def resolver_recurso(uri, rel=None):
    """Converte /static/... (e /media/...) no ficheiro real, para o xhtml2pdf os ler."""
    import os

    from django.conf import settings

    if os.path.isfile(uri):
        return uri
    static_url = settings.STATIC_URL or "/static/"
    if uri.startswith(static_url):
        caminho = finders.find(uri[len(static_url):])
        if isinstance(caminho, (list, tuple)):
            caminho = caminho[0] if caminho else None
        if caminho:
            return str(caminho)
    media_url = getattr(settings, "MEDIA_URL", "") or ""
    if media_url and uri.startswith(media_url):
        caminho = os.path.join(str(settings.MEDIA_ROOT), uri[len(media_url):])
        if os.path.isfile(caminho):
            return caminho
    return uri


def html_para_pdf(template, contexto):
    contexto = {**contexto, "logo": caminho_logo()}
    html = render_to_string(template, contexto)
    saida = BytesIO()
    resultado = pisa.CreatePDF(html, dest=saida, encoding="utf-8", link_callback=resolver_recurso)
    if resultado.err:
        raise RuntimeError("Não foi possível gerar o PDF.")
    return saida.getvalue()