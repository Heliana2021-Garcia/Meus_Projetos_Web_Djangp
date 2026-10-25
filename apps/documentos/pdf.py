import base64
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from apps.estudantes.models import PerfilEstudante

from . import config


def _logo_data_uri():
    """Logótipo opcional em static/img/logo_instic.png (PNG)."""
    caminho = Path(settings.BASE_DIR) / "static" / "img" / "logo_instic.png"
    if not caminho.is_file():
        return None
    dados = base64.b64encode(caminho.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{dados}"


def gerar_pdf(carta):
    candidatura = carta.candidatura
    vaga = candidatura.vaga
    empresa = vaga.empresa
    estudante = candidatura.estudante

    html = render_to_string(
        "pdf/carta_encaminhamento.html",
        {
            "carta": carta,
            "vaga": vaga,
            "empresa": empresa,
            "responsavel": empresa.utilizador.get_full_name(),
            "estudante": estudante,
            "nome_estudante": estudante.utilizador.get_full_name() or estudante.utilizador.username,
            "ano_minimo": PerfilEstudante.ANO_MINIMO_CANDIDATURA,
            "media_minima": PerfilEstudante.MEDIA_MINIMA_CANDIDATURA,
            "config": config,
            "logo": _logo_data_uri(),
        },
    )

    saida = BytesIO()
    resultado = pisa.CreatePDF(html, dest=saida, encoding="utf-8")
    if resultado.err:
        raise RuntimeError("Não foi possível gerar o PDF da carta.")
    return saida.getvalue()