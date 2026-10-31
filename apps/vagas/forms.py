from django import forms
from django.utils import timezone

from apps.core.forms import EstiloCamposMixin

from .models import Vaga


class VagaForm(EstiloCamposMixin, forms.ModelForm):
    class Meta:
        model = Vaga
        fields = (
            "titulo", "area", "tipo_estagio", "descricao", "requisitos", "documentos_exigidos",
            "cursos", "tecnologias", "numero_vagas", "localizacao", "modalidade",
            "duracao_meses", "data_limite", "fase_teste", "fase_curriculo", "fase_entrevista",
        )
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 5}),
            "requisitos": forms.Textarea(attrs={"rows": 4}),
            "documentos_exigidos": forms.Textarea(attrs={"rows": 3}),
            "cursos": forms.CheckboxSelectMultiple,
            "tecnologias": forms.CheckboxSelectMultiple,
            "data_limite": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def clean_numero_vagas(self):
        valor = self.cleaned_data["numero_vagas"]
        if valor < 1:
            raise forms.ValidationError("Indique pelo menos 1 lugar.")
        return valor

    def clean_duracao_meses(self):
        valor = self.cleaned_data["duracao_meses"]
        if valor < 1:
            raise forms.ValidationError("A duração mínima é de 1 mês.")
        return valor

    def clean_data_limite(self):
        data = self.cleaned_data.get("data_limite")
        if data and data < timezone.localdate():
            raise forms.ValidationError("A data limite não pode estar no passado.")
        return data