from django.urls import path

from . import views

app_name = "relatorios"

urlpatterns = [
    path("", views.PainelAdminView.as_view(), name="painel"),
    path("empresas/<int:pk>/validar-nif/", views.ValidarNifView.as_view(), name="validar_nif"),
    path("relatorios/", views.DashboardView.as_view(), name="dashboard"),
    path("relatorios/exportar/", views.ExportarColocacoesView.as_view(), name="exportar"),
]