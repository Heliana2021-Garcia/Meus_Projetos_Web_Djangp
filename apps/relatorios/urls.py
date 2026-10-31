from django.urls import path

from . import views

app_name = "relatorios"

urlpatterns = [
    path("", views.PainelAdminView.as_view(), name="painel"),
    path("empresas/<int:pk>/validar-nif/", views.ValidarNifView.as_view(), name="validar_nif"),
    path("relatorios/", views.DashboardView.as_view(), name="dashboard"),
    path("estagios/", views.EstagiosGestaoView.as_view(), name="estagios"),
    path("estudantes/", views.EstudantesPendentesView.as_view(), name="estudantes_pendentes"),
    path("estudantes/<int:pk>/aprovar/", views.AprovarEstudanteView.as_view(), name="aprovar_estudante"),
    path("estudantes/<int:pk>/devolver/", views.DevolverEstudanteView.as_view(), name="devolver_estudante"),
    path("vagas/", views.VagasEmAnaliseView.as_view(), name="vagas_analise"),
    path("vagas/<int:pk>/aprovar/", views.AprovarVagaView.as_view(), name="aprovar_vaga"),
    path("vagas/<int:pk>/devolver/", views.DevolverVagaView.as_view(), name="devolver_vaga"),
    path("relatorios/exportar/", views.ExportarColocacoesView.as_view(), name="exportar"),
]

from . import views_estagios  # noqa: E402

urlpatterns += [
    path("estagios/relatorio/", views_estagios.RelatorioEstagiosView.as_view(), name="relatorio_estagios"),
    path("estagios/relatorio/csv/", views_estagios.ExportarEstagiosCsvView.as_view(), name="relatorio_estagios_csv"),
    path("estagios/relatorio/pdf/", views_estagios.ExportarEstagiosPdfView.as_view(), name="relatorio_estagios_pdf"),
]

from . import views_decisoes  # noqa: E402

urlpatterns += [
    path("decisoes/", views_decisoes.DecisoesView.as_view(), name="decisoes"),
]


from .views_gestao import RelatorioGestaoView  # noqa: E402

urlpatterns += [
    path("gestao/", RelatorioGestaoView.as_view(), name="relatorio_gestao"),
]
