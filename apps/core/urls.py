from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.ListaNotificacoesView.as_view(), name="notificacoes"),
    path("<int:pk>/abrir/", views.AbrirNotificacaoView.as_view(), name="abrir"),
    path("ler-todas/", views.MarcarTodasLidasView.as_view(), name="ler_todas"),
]