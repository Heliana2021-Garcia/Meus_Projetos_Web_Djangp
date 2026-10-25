from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class TipoRequeridoMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Só deixa entrar utilizadores cujo tipo esteja em `tipos_permitidos`."""

    tipos_permitidos = ()

    def test_func(self):
        return self.request.user.tipo in self.tipos_permitidos