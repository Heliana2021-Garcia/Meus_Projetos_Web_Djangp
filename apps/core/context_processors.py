def notificacoes(request):
    utilizador = getattr(request, "user", None)
    if utilizador is not None and utilizador.is_authenticated:
        return {
            "notificacoes_nao_lidas": utilizador.notificacoes.filter(lida=False).count()
        }
    return {}