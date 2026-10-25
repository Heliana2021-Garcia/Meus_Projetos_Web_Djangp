from django.urls import path

from . import views

app_name = "candidaturas"

urlpatterns = [
    # estudante
    path("", views.MinhasCandidaturasView.as_view(), name="minhas"),
    # empresa
    path("empresa/vaga/<int:pk>/", views.KanbanVagaView.as_view(), name="kanban"),
    path("empresa/<int:pk>/mover/", views.MoverCandidaturaView.as_view(), name="mover"),
    path("empresa/<int:pk>/concluir/", views.ConcluirEstagioView.as_view(), name="concluir"),
]