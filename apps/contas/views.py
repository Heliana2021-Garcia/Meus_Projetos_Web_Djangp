from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.generic import FormView

from .forms import RegistoEmpresaForm, RegistoEstudanteForm
from .models import Utilizador

PAINEL_POR_TIPO = {
    Utilizador.Tipo.ADMINISTRADOR: "relatorios:painel",
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
        login(self.request, utilizador)
        messages.success(self.request, self.mensagem_sucesso)
        return redirect("contas:inicio")


class RegistoEstudanteView(RegistoBaseView):
    form_class = RegistoEstudanteForm
    mensagem_sucesso = "Conta de estudante criada. Complete o seu perfil para se candidatar."
    extra_context = {
        "titulo_pagina": "Registo de estudante",
        "subtitulo_pagina": "Crie a sua conta para se candidatar a estágios.",
    }


class RegistoEmpresaView(RegistoBaseView):
    form_class = RegistoEmpresaForm
    mensagem_sucesso = "Conta de empresa criada. O NIF será validado pela administração."
    extra_context = {
        "titulo_pagina": "Registo de empresa",
        "subtitulo_pagina": "Registe a sua empresa para publicar vagas de estágio.",
    }