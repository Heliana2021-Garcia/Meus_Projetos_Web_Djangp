"""Registo de decisões: grava quem fez o quê, quando, nas acções relevantes."""
import logging

from .models import RegistoDecisao

logger = logging.getLogger(__name__)

ACCOES = {
    "relatorios:aprovar_estudante": "Registo de estudante aprovado",
    "relatorios:devolver_estudante": "Registo de estudante devolvido para correcção",
    "candidaturas:mover": "Fase da candidatura alterada",
    "candidaturas:atribuir_orientador": "Orientador atribuído",
    "candidaturas:confirmar_inicio": "Início do estágio confirmado",
    "candidaturas:interromper": "Estágio interrompido",
    "candidaturas:decidir": "Decisão sobre registo ou relatório do estágio",
    "candidaturas:avaliar": "Avaliação do estágio registada",
    "candidaturas:validar_conclusao": "Conclusão do estágio validada",
    "candidaturas:efectivacao": "Efectivação registada",
}
# Pedidos que respondem 200 em caso de sucesso (JSON do Kanban)
RESPOSTA_DIRECTA = {"candidaturas:mover"}
CAMPOS_DETALHE = ("motivo", "comentario", "acao", "feedback", "resultado", "estado", "fase", "destino")


def _rotulo(view_name):
    if view_name in ACCOES:
        return ACCOES[view_name]
    espaco, _, nome = view_name.rpartition(":")
    if espaco == "relatorios":
        if "nif" in nome:
            return "NIF da empresa validado"
        if "aprovar" in nome:
            return f"Aprovação ({nome})"
        if "devolver" in nome:
            return f"Devolução para correcção ({nome})"
    return None


def registar_pedido(request, response):
    if request.method != "POST":
        return
    utilizador = getattr(request, "user", None)
    if utilizador is None or not utilizador.is_authenticated:
        return
    resolvido = request.resolver_match
    if resolvido is None or not resolvido.view_name:
        return
    rotulo = _rotulo(resolvido.view_name)
    if not rotulo:
        return

    if resolvido.view_name in RESPOSTA_DIRECTA:
        sucesso = response.status_code < 400
    else:
        sucesso = response.status_code in (301, 302, 303)  # as vistas redireccionam quando correu bem
    if not sucesso:
        return
    pendentes = getattr(getattr(request, "_messages", None), "_queued_messages", [])
    if any(getattr(m, "level", 0) >= 40 for m in pendentes):  # mensagem de erro: nada foi decidido
        return

    detalhe = "; ".join(
        f"{campo}: {request.POST[campo][:200]}" for campo in CAMPOS_DETALHE if request.POST.get(campo)
    )
    argumentos = ", ".join(f"{k}={v}" for k, v in resolvido.kwargs.items())
    RegistoDecisao.objects.create(
        utilizador=utilizador,
        nome_utilizador=f"{utilizador.get_full_name() or utilizador.username} ({utilizador.get_tipo_display()})",
        accao=rotulo,
        referencia=f"{resolvido.view_name} {argumentos}".strip(),
        detalhe=detalhe,
    )