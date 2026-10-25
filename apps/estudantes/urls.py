from django.urls import path

from . import views

app_name = "estudantes"

urlpatterns = [
    path("", views.PainelEstudanteView.as_view(), name="painel"),
    path("perfil/", views.PerfilEstudanteUpdateView.as_view(), name="perfil"),
]