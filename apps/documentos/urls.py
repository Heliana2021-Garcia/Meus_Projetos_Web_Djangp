from django.urls import path

from . import views

app_name = "documentos"

urlpatterns = [
    path("carta/<int:pk>/", views.DescarregarCartaView.as_view(), name="descarregar"),
    path("emitir/<int:pk>/", views.EmitirCartaView.as_view(), name="emitir"),
]