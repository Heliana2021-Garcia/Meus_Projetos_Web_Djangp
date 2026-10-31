from django import forms
from django.contrib.auth import get_user_model


def clean_email_unico(self):
    """clean_email partilhado: o email identifica a conta, por isso não pode repetir-se."""
    email = (self.cleaned_data.get("email") or "").strip().lower()
    if email:
        existente = get_user_model().objects.filter(email__iexact=email)
        pk = getattr(getattr(self, "instance", None), "pk", None)
        if pk:
            existente = existente.exclude(pk=pk)
        if existente.exists():
            raise forms.ValidationError("Já existe uma conta com este email.")
    return email