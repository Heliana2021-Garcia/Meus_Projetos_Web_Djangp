from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Autentica com email e palavra-passe (sem distinguir maiúsculas de minúsculas)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        email = username if username is not None else kwargs.get("email")
        if not email or password is None:
            return None
        candidatos = list(UserModel.objects.filter(email__iexact=email.strip())[:2])
        if len(candidatos) != 1:  # sem conta, ou email repetido: nunca se adivinha
            UserModel().set_password(password)  # tempo de resposta semelhante
            return None
        utilizador = candidatos[0]
        if utilizador.check_password(password) and self.user_can_authenticate(utilizador):
            return utilizador
        return None