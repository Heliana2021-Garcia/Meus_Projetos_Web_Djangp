from django.urls import path

from . import views, views_orientador

app_name = "empresas"

urlpatterns = [
    path("", views.PainelEmpresaView.as_view(), name="painel"),
    path("orientadores/", views_orientador.OrientadoresEmpresaView.as_view(), name="orientadores"),
    path("orientador/", views_orientador.PainelOrientadorView.as_view(), name="painel_orientador"),
]