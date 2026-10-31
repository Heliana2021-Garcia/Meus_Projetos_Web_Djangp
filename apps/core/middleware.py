import logging

from .auditoria import registar_pedido

logger = logging.getLogger(__name__)


class AuditoriaMiddleware:
    """Regista as decisões relevantes depois de a vista responder."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        try:
            registar_pedido(request, resposta)
        except Exception:  # a auditoria nunca deve impedir o pedido do utilizador
            logger.exception("Falha ao registar a decisão")
        return resposta