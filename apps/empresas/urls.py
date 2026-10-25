from django.urls import path

from . import views

app_name = "empresas"

urlpatterns = [
    path("", views.PainelEmpresaView.as_view(), name="painel"),
]