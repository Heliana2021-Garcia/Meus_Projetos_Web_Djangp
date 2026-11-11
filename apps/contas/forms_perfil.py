"""Formulários do perfil: cada secção da página «Editar o meu perfil» tem o seu."""
from django import forms
from django.contrib.auth.forms import PasswordChangeForm

from apps.core.forms import EstiloCamposMixin
from apps.empresas.models import Empresa, Orientador

from .emails import clean_email_unico
from .models import Utilizador


class ContaForm(EstiloCamposMixin, forms.ModelForm):
    """Nome, apelido e email (o email é também o que se usa para entrar)."""

    class Meta:
        model = Utilizador
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Nome", "last_name": "Apelido", "email": "Email"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.required = True
        # O ModelForm altera a instância ao validar: guarda-se o que a conta tinha antes.
        self._email_antigo = (self.instance.email or "").strip().lower()
        self._username_antigo = (self.instance.username or "").strip().lower()

    def clean_email(self):
        email = clean_email_unico(self)
        if email:
            em_uso = Utilizador.objects.filter(username__iexact=email).exclude(pk=self.instance.pk)
            if em_uso.exists():
                raise forms.ValidationError("Já existe uma conta com este email.")
        return email

    def save(self, commit=True):
        utilizador = super().save(commit=False)
        # Nos registos de estudantes e empresas o nome de utilizador é o próprio email:
        # mantém-se assim. Os orientadores têm o nome de utilizador que a empresa lhes deu.
        if self._username_antigo == self._email_antigo:
            utilizador.username = utilizador.email[:150]
        if commit:
            utilizador.save()
        return utilizador


class SenhaForm(EstiloCamposMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Palavra-passe actual"
        self.fields["new_password1"].label = "Nova palavra-passe"
        self.fields["new_password2"].label = "Confirmar a nova palavra-passe"
        self.fields["old_password"].widget.attrs.pop("autofocus", None)


class EmpresaPerfilForm(EstiloCamposMixin, forms.ModelForm):
    """O NIF não se altera aqui: foi validado pela coordenação."""

    class Meta:
        model = Empresa
        fields = ("nome", "sector", "telefone", "endereco")
        labels = {"nome": "Nome da empresa"}


class OrientadorPerfilForm(EstiloCamposMixin, forms.ModelForm):
    class Meta:
        model = Orientador
        fields = ("cargo",)
