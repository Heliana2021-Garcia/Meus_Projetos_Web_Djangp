from django.urls import reverse

from apps.core.notificacoes import notificar_gestao

from .models import DocumentoEstudante, PerfilEstudante


def submeter_documentos(perfil, dados):
    """Guarda os documentos enviados e, se o registo estava devolvido, volta a submetê-lo."""
    if dados.get("declaracao_notas"):
        perfil.guardar_documento(DocumentoEstudante.Tipo.DECLARACAO, dados["declaracao_notas"])
    if dados.get("declaracao_frequencia"):
        perfil.guardar_documento(DocumentoEstudante.Tipo.FREQUENCIA, dados["declaracao_frequencia"])
    if perfil.registo_estado == PerfilEstudante.Registo.DEVOLVIDO:
        perfil.resubmeter_registo()
        notificar_gestao(
            "Registo corrigido",
            f"{perfil.utilizador} voltou a submeter os documentos para validação.",
            reverse("relatorios:estudantes_pendentes"),
        )
