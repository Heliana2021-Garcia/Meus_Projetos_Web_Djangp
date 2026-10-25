from django import forms
from django.core.files.uploadedfile import UploadedFile

from apps.core.forms import EstiloCamposMixin

from .models import PerfilEstudante

TAMANHO_MAXIMO_CV = 5 * 1024 * 1024  # 5 MB


class PerfilEstudanteForm(EstiloCamposMixin, forms.ModelForm):
    class Meta:
        model = PerfilEstudante
        fields = ("resumo", "curriculo", "tecnologias")
        widgets = {
            "resumo": forms.Textarea(attrs={"rows": 4}),
            "tecnologias": forms.CheckboxSelectMultiple,
        }

    def clean_curriculo(self):
        ficheiro = self.cleaned_data.get("curriculo")
        if isinstance(ficheiro, UploadedFile):
            if not ficheiro.name.lower().endswith(".pdf"):
                raise forms.ValidationError("O currículo tem de ser um ficheiro PDF.")
            if ficheiro.size > TAMANHO_MAXIMO_CV:
                raise forms.ValidationError("O currículo não pode ter mais de 5 MB.")
        return ficheiro