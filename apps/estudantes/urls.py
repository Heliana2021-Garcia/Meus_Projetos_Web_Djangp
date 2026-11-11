from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "estudantes"

urlpatterns = [
    path("", views.PainelEstudanteView.as_view(), name="painel"),
    path("perfil/", RedirectView.as_view(pattern_name="contas:editar_perfil"), name="perfil"),
    path("documentos/", views.DocumentosEstudanteView.as_view(), name="documentos"),
    path("documentos/<int:pk>/", views.DescarregarDocumentoView.as_view(), name="documento"),
]