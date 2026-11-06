from django.urls import path

from . import views, views_avaliacao, views_certificado, views_estagio

app_name = "candidaturas"

urlpatterns = [
    # estudante
    path("", views.MinhasCandidaturasView.as_view(), name="minhas"),
    # empresa
    path("empresa/vaga/<int:pk>/", views.KanbanVagaView.as_view(), name="kanban"),
    path("empresa/<int:pk>/mover/", views.MoverCandidaturaView.as_view(), name="mover"),
    # estágio
    path("estagio/", views.EstagioEstudanteView.as_view(), name="estagio"),
    path("empresa/estagios/", views.EstagiosEmpresaView.as_view(), name="estagios"),
    path("<int:pk>/orientador/", views.AtribuirOrientadorView.as_view(), name="atribuir_orientador"),
    path("<int:pk>/confirmar-inicio/", views.ConfirmarInicioView.as_view(), name="confirmar_inicio"),
    path("<int:pk>/interromper/", views.InterromperEstagioView.as_view(), name="interromper"),
    # diário, relatórios e acompanhamento
    path("estagio/diario/", views_estagio.DiarioView.as_view(), name="diario"),
    path("estagio/diario/<int:pk>/editar/", views_estagio.EditarRegistoView.as_view(), name="registo_editar"),
    path("estagio/relatorios/", views_estagio.RelatoriosEstudanteView.as_view(), name="relatorios"),
    path("estagio/relatorios/<slug:tipo>/", views_estagio.RelatorioEstudanteView.as_view(), name="relatorio"),
    path("<int:pk>/acompanhar/", views_estagio.AcompanharEstagioView.as_view(), name="acompanhar"),
    path("<int:pk>/efectivacao/", views_estagio.RegistarEfectivacaoView.as_view(), name="efectivacao"),
    # avaliação e conclusão
    path("estagio/avaliacao/", views_avaliacao.MinhaAvaliacaoView.as_view(), name="minha_avaliacao"),
    path("<int:pk>/avaliacao/", views_avaliacao.AvaliacaoEstagioView.as_view(), name="avaliacao"),
    path("estagio/avaliar-orientador/", views_avaliacao.AvaliarOrientadorView.as_view(), name="avaliar_orientador"),
    path("<int:pk>/validar-conclusao/", views_avaliacao.ValidarConclusaoView.as_view(), name="validar_conclusao"),
    path("<int:pk>/certificado/", views_certificado.CertificadoView.as_view(), name="certificado"),
    path("acompanhamento/<str:tipo>/<int:pk>/decidir/", views_estagio.DecidirView.as_view(), name="decidir"),
]
