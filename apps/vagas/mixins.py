from django.utils.functional import cached_property

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.empresas.models import Empresa
from apps.estudantes.models import PerfilEstudante


class EmpresaRequeridaMixin(TipoRequeridoMixin):
    tipos_permitidos = (Utilizador.Tipo.EMPRESA,)

    @cached_property
    def empresa(self):
        return Empresa.objects.filter(utilizador=self.request.user).first()

    def test_func(self):
        return super().test_func() and self.empresa is not None


class EstudanteRequeridoMixin(TipoRequeridoMixin):
    tipos_permitidos = (Utilizador.Tipo.ESTUDANTE,)

    @cached_property
    def perfil(self):
        return (
            PerfilEstudante.objects.select_related("curso")
            .filter(utilizador=self.request.user)
            .first()
        )

    def test_func(self):
        return super().test_func() and self.perfil is not None