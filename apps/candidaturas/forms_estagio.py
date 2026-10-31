from django import forms
from django.utils import timezone

from apps.core.forms import EstiloCamposMixin

from .models import RegistoDiario, RelatorioEstagio


class RegistoDiarioForm(EstiloCamposMixin, forms.ModelForm):
    class Meta:
        model = RegistoDiario
        fields = ("data", "descricao", "competencias", "observacoes")
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "competencias": forms.Textarea(attrs={"rows": 3}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidatura = candidatura
        self.instance.candidatura = candidatura

    def clean_data(self):
        data = self.cleaned_data["data"]
        if data > timezone.localdate():
            raise forms.ValidationError("A data não pode ser futura.")
        inicio = self.candidatura.data_inicio
        if inicio and data < inicio:
            raise forms.ValidationError("A data não pode ser anterior ao início do estágio.")
        repetido = RegistoDiario.objects.filter(candidatura=self.candidatura, data=data)
        if repetido.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe um registo para esta data. Edite-o na lista.")
        return data

    def save(self, commit=True):
        registo = super().save(commit=False)
        registo.estado = RegistoDiario.Estado.SUBMETIDO
        if commit:
            registo.save()
            registo.avisar_orientador()
        return registo


class RelatorioForm(EstiloCamposMixin, forms.ModelForm):
    class Meta:
        model = RelatorioEstagio
        fields = ("titulo", "conteudo")
        widgets = {"conteudo": forms.Textarea(attrs={"rows": 14})}

    def __init__(self, *args, candidatura, tipo, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.candidatura = candidatura
        self.instance.tipo = tipo

    def save(self, commit=True):
        relatorio = super().save(commit=False)
        relatorio.estado = RelatorioEstagio.Estado.SUBMETIDO
        if commit:
            relatorio.save()
            relatorio.avisar_orientador()
        return relatorio