from django.conf import settings
from django.core.mail import send_mail

from .models import Notificacao


def notificar(destinatario, titulo, mensagem="", url=""):
    """Cria a notificação no sistema e, se configurado, envia também um email."""
    notificacao = Notificacao.objects.create(
        destinatario=destinatario, titulo=titulo, mensagem=mensagem, url=url
    )

    if getattr(settings, "NOTIFICAR_POR_EMAIL", False) and destinatario.email:
        corpo = mensagem or titulo
        if url:
            corpo += f"\n\n{settings.SITE_URL}{url}"
        send_mail(
            f"[SIGEST] {titulo}",
            corpo,
            settings.DEFAULT_FROM_EMAIL,
            [destinatario.email],
            fail_silently=True,
        )
    return notificacao

def notificar_gestao(titulo, mensagem="", url=""):
    """Avisa todos os coordenadores e administradores activos."""
    from django.contrib.auth import get_user_model

    Utilizador = get_user_model()
    for destinatario in Utilizador.objects.filter(
        tipo__in=[Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR], is_active=True
    ):
        notificar(destinatario, titulo, mensagem, url)
