from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class UtilizadorManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("tipo", Utilizador.Tipo.ADMINISTRADOR)
        return super().create_superuser(username, email, password, **extra_fields)


class Utilizador(AbstractUser):
    class Tipo(models.TextChoices):
        ADMINISTRADOR = "ADMIN", "Administrador técnico"
        COORDENADOR = "COORDENADOR", "Coordenador institucional"
        ORIENTADOR = "ORIENTADOR", "Orientador empresarial"
        ESTUDANTE = "ESTUDANTE", "Estudante"
        EMPRESA = "EMPRESA", "Empresa"

    email = models.EmailField("email", unique=True)
    tipo = models.CharField(
        "tipo de utilizador",
        max_length=15,
        choices=Tipo.choices,
        default=Tipo.ESTUDANTE,
    )

    objects = UtilizadorManager()

    class Meta:
        verbose_name = "utilizador"
        verbose_name_plural = "utilizadores"

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def e_administrador(self):
        return self.tipo == self.Tipo.ADMINISTRADOR

    @property
    def e_estudante(self):
        return self.tipo == self.Tipo.ESTUDANTE

    @property
    def e_empresa(self):
        return self.tipo == self.Tipo.EMPRESA

    @property
    def e_coordenador(self):
        return self.tipo == self.Tipo.COORDENADOR

    @property
    def e_gestao(self):
        """Quem valida registos, empresas e vagas."""
        return self.tipo in (self.Tipo.ADMINISTRADOR, self.Tipo.COORDENADOR)

    @property
    def e_orientador(self):
        return self.tipo == self.Tipo.ORIENTADOR
