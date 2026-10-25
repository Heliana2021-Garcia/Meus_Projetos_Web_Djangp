from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.contas.urls")),
    path("estudante/", include("apps.estudantes.urls")),
    path("empresa/", include("apps.empresas.urls")),
    path("administracao/", include("apps.relatorios.urls")),
    path("vagas/", include("apps.vagas.urls")),
    path("candidaturas/", include("apps.candidaturas.urls")),
    path("documentos/", include("apps.documentos.urls")),
    path("notificacoes/", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)