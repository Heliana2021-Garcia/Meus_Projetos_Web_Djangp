from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django import forms

from apps.contas.models import Utilizador
from apps.core.forms import EstiloCamposMixin

from .models import Orientador


class OrientadorForm(EstiloCamposMixin, UserCreationForm):
    cargo = forms.CharField(label="Cargo / função", max_length=100, required=False)

    field_order = [
        "first_name", "last_name", "cargo", "username", "email", "password1", "password2",
    ]

    class Meta(UserCreationForm.Meta):
        model = Utilizador
        fields = ("first_name", "last_name", "username", "email")

    def __init__(self, *args, empresa, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        self.fields["first_name"].required = True
        self.fields["email"].required = True
        self.fields["last_name"].required = True
        self.fields["first_name"].label = "Nome"
        self.fields["last_name"].label = "Apelido"

    @transaction.atomic
    def save(self, commit=True):
        utilizador = super().save(commit=False)
        utilizador.tipo = Utilizador.Tipo.ORIENTADOR
        utilizador.save()
        return Orientador.objects.create(
            utilizador=utilizador, empresa=self.empresa, cargo=self.cleaned_data["cargo"]
        )

from apps.contas.emails import clean_email_unico  # noqa: E402

OrientadorForm.clean_email = clean_email_unico
