from django.urls import path

from . import views

app_name = "vagas"

urlpatterns = [
    # estudante
    path("", views.FeedVagasView.as_view(), name="feed"),
    path("<int:pk>/", views.VagaDetalheView.as_view(), name="detalhe"),
    path("<int:pk>/candidatar/", views.CandidatarView.as_view(), name="candidatar"),
    # empresa
    path("empresa/", views.MinhasVagasView.as_view(), name="minhas"),
    path("empresa/nova/", views.VagaCreateView.as_view(), name="nova"),
    path("empresa/<int:pk>/editar/", views.VagaUpdateView.as_view(), name="editar"),
    path("empresa/<int:pk>/publicar/", views.PublicarVagaView.as_view(), name="publicar"),
    path("empresa/<int:pk>/encerrar/", views.EncerrarVagaView.as_view(), name="encerrar"),
]