from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.core.notificacoes import notificar_gestao
from apps.estudantes.forms import DocumentosEstudanteForm, PerfilEstudanteForm
from apps.estudantes.models import DocumentoEstudante, PerfilEstudante
from apps.estudantes.servicos import submeter_documentos

from .forms_perfil import ContaForm, EmpresaPerfilForm, OrientadorPerfilForm, SenhaForm
from .models import Utilizador


def _perfis(utilizador):
    """O perfil específico do tipo de utilizador (ou None, se não existir)."""
    return (
        getattr(utilizador, "perfil_estudante", None),
        getattr(utilizador, "empresa", None),
        getattr(utilizador, "orientador", None),
    )


class PerfilView(LoginRequiredMixin, TemplateView):
    """Mostra ao utilizador as informações da sua conta."""

    template_name = "contas/perfil.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        estudante, empresa, orientador = _perfis(self.request.user)
        contexto["estudante"] = estudante
        contexto["empresa"] = empresa
        contexto["orientador"] = orientador
        if estudante:
            contexto["documentos"] = estudante.documentos.all()
            contexto["tecnologias"] = estudante.tecnologias.all()
        if orientador:
            contexto["empresa_orientador"] = orientador.empresa
        return contexto


class EditarPerfilView(LoginRequiredMixin, View):
    """Uma página, várias secções: cada secção é um formulário com o seu botão «Guardar»."""

    template_name = "contas/perfil_editar.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.estudante, self.empresa, self.orientador = _perfis(request.user)
        return super().dispatch(request, *args, **kwargs)

    # --- construção dos formulários -------------------------------------------
    @property
    def documentos_editaveis(self):
        return bool(self.estudante) and self.estudante.registo_estado != PerfilEstudante.Registo.APROVADO

    def _formularios(self, request, ligado=None):
        """Devolve {nome: formulário}; só o formulário «ligado» recebe os dados enviados."""

        def dados(nome):
            if ligado != nome:
                return {}
            return {"data": request.POST, "files": request.FILES}

        formularios = {
            # instância nova: um formulário inválido não pode alterar o nome que aparece no cabeçalho
            "conta": ContaForm(
                instance=Utilizador.objects.get(pk=request.user.pk), prefix="conta", **dados("conta")
            ),
        }
        if self.estudante:
            formularios["perfil"] = PerfilEstudanteForm(
                instance=self.estudante, prefix="perfil", **dados("perfil")
            )
        elif self.empresa:
            formularios["perfil"] = EmpresaPerfilForm(
                instance=self.empresa, prefix="perfil", **dados("perfil")
            )
        elif self.orientador:
            formularios["perfil"] = OrientadorPerfilForm(
                instance=self.orientador, prefix="perfil", **dados("perfil")
            )
        if self.documentos_editaveis:
            formularios["documentos"] = DocumentosEstudanteForm(
                perfil=self.estudante, prefix="documentos", **dados("documentos")
            )
        formularios["senha"] = SenhaForm(request.user, prefix="senha", **dados("senha"))
        return formularios

    def _contexto(self, formularios, seccao_activa=""):
        return {
            "formularios": formularios,
            "seccao_activa": seccao_activa,
            "estudante": self.estudante,
            "empresa": self.empresa,
            "orientador": self.orientador,
            "documentos": self.estudante.documentos.all() if self.estudante else [],
            "documentos_editaveis": self.documentos_editaveis,
        }

    # --- pedidos ---------------------------------------------------------------
    def get(self, request):
        return render(request, self.template_name, self._contexto(self._formularios(request)))

    def post(self, request):
        accao = request.POST.get("accao", "")
        if accao == "documentos" and self.estudante and not self.documentos_editaveis:
            messages.info(request, "O seu registo já foi aprovado. Os documentos não podem ser alterados.")
            return redirect(f"{reverse('contas:editar_perfil')}#documentos")

        formularios = self._formularios(request, ligado=accao)
        formulario = formularios.get(accao)
        if formulario is None:
            messages.error(request, "Pedido inválido.")
            return redirect("contas:editar_perfil")

        if not formulario.is_valid():
            messages.error(request, "Corrija os erros assinalados e volte a guardar.")
            return render(request, self.template_name, self._contexto(formularios, accao), status=200)

        self._guardar(request, accao, formulario)
        return redirect(f"{reverse('contas:editar_perfil')}#{accao}")

    def _guardar(self, request, accao, formulario):
        if accao == "conta":
            formulario.save()
            messages.success(request, "Dados da conta actualizados.")
        elif accao == "perfil":
            formulario.save()
            messages.success(request, "Perfil actualizado.")
        elif accao == "senha":
            utilizador = formulario.save()
            update_session_auth_hash(request, utilizador)  # não termina a sessão actual
            messages.success(request, "Palavra-passe alterada.")
        elif accao == "documentos":
            submeter_documentos(self.estudante, formulario.cleaned_data)
            messages.success(request, "Documentos enviados. A coordenação vai analisá-los.")
