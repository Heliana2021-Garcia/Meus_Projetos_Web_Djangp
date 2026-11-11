from django.contrib.auth import views as auth_views
from django.urls import path

from . import views, views_perfil
from .forms import EntrarForm

app_name = "contas"

urlpatterns = [
    path("", views.PaginaPublicaView.as_view(), name="publica"),
    path("painel/", views.inicio, name="inicio"),
    path(
        "entrar/",
        auth_views.LoginView.as_view(
            template_name="contas/entrar.html",
            authentication_form=EntrarForm,
            redirect_authenticated_user=True,
        ),
        name="entrar",
    ),
    path("sair/", auth_views.LogoutView.as_view(), name="sair"),
    path("perfil/", views_perfil.PerfilView.as_view(), name="perfil"),
    path("perfil/editar/", views_perfil.EditarPerfilView.as_view(), name="editar_perfil"),
    path("registo/estudante/", views.RegistoEstudanteView.as_view(), name="registo_estudante"),
    path("registo/empresa/", views.RegistoEmpresaView.as_view(), name="registo_empresa"),
]