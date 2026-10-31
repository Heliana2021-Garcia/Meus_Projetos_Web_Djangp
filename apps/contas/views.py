from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from .forms import RegistoEmpresaForm, RegistoEstudanteForm
from apps.core.notificacoes import notificar_gestao
from apps.estudantes.models import PerfilEstudante

from .models import Utilizador

PAINEL_POR_TIPO = {
    Utilizador.Tipo.ADMINISTRADOR: "relatorios:painel",
    Utilizador.Tipo.COORDENADOR: "relatorios:painel",
    Utilizador.Tipo.ORIENTADOR: "empresas:painel_orientador",
    Utilizador.Tipo.ESTUDANTE: "estudantes:painel",
    Utilizador.Tipo.EMPRESA: "empresas:painel",
}


@login_required
def inicio(request):
    return redirect(PAINEL_POR_TIPO[request.user.tipo])


class RegistoBaseView(FormView):
    template_name = "contas/registo.html"
    mensagem_sucesso = ""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("contas:inicio")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        utilizador = form.save()
        if utilizador.tipo == Utilizador.Tipo.ESTUDANTE:
            notificar_gestao(
                "Novo registo de estudante",
                f"{utilizador.get_full_name()} registou-se e aguarda validação.",
                reverse("relatorios:estudantes_pendentes"),
            )
        login(self.request, utilizador)
        messages.success(self.request, self.mensagem_sucesso)
        return redirect("contas:inicio")


class RegistoEstudanteView(RegistoBaseView):
    form_class = RegistoEstudanteForm
    mensagem_sucesso = "Conta criada. A coordenação vai validar o seu registo e os documentos antes de poder candidatar-se."
    extra_context = {
        "titulo_pagina": "Registo de estudante",
        "subtitulo_pagina": "Crie a sua conta para se candidatar a estágios.",
    }


class RegistoEmpresaView(RegistoBaseView):
    form_class = RegistoEmpresaForm
    mensagem_sucesso = "Pedido de parceria enviado ao INSTIC. Será avisado quando for aprovado."
    extra_context = {
        "titulo_pagina": "Pedido de parceria",
        "subtitulo_pagina": "Peça parceria ao INSTIC. Depois de aprovada, poderá submeter vagas de estágio.",
    }

class PaginaPublicaView(TemplateView):
    template_name = "publico/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["ano_minimo"] = PerfilEstudante.ANO_MINIMO_CANDIDATURA
        contexto["media_minima"] = PerfilEstudante.MEDIA_MINIMA_CANDIDATURA
        return contexto
