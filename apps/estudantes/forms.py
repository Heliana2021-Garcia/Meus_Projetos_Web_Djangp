from django import forms
from django.core.files.uploadedfile import UploadedFile

from apps.core.forms import EstiloCamposMixin

from .models import DocumentoEstudante, PerfilEstudante
from .validadores import validar_documento

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

class DocumentosEstudanteForm(EstiloCamposMixin, forms.Form):
    declaracao_notas = forms.FileField(label="Declaração com notas", required=False,
                                       help_text="PDF, PNG ou JPG, até 5 MB.")
    bilhete_identidade = forms.FileField(label="Bilhete de identidade", required=False,
                                         help_text="PDF, PNG ou JPG, até 5 MB.")

    def __init__(self, *args, perfil, **kwargs):
        super().__init__(*args, **kwargs)
        self.perfil = perfil
        existentes = set(perfil.documentos.values_list("tipo", flat=True))
        if DocumentoEstudante.Tipo.DECLARACAO not in existentes:
            self.fields["declaracao_notas"].required = True
        if DocumentoEstudante.Tipo.BI not in existentes:
            self.fields["bilhete_identidade"].required = True

    def clean_declaracao_notas(self):
        ficheiro = self.cleaned_data.get("declaracao_notas")
        return validar_documento(ficheiro) if ficheiro else ficheiro

    def clean_bilhete_identidade(self):
        ficheiro = self.cleaned_data.get("bilhete_identidade")
        return validar_documento(ficheiro) if ficheiro else ficheiro

    def clean(self):
        dados = super().clean()
        if not self.errors and not dados.get("declaracao_notas") and not dados.get("bilhete_identidade"):
            raise forms.ValidationError("Seleccione pelo menos um ficheiro para enviar.")
        return dados
