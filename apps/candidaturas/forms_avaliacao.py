from django import forms

from apps.core.forms import EstiloCamposMixin

from .models import AvaliacaoMensal


class AvaliacaoMensalForm(EstiloCamposMixin, forms.ModelForm):
    class Meta:
        model = AvaliacaoMensal
        fields = ("nota", "comentario")
        labels = {"nota": "Nota (0 a 20)", "comentario": "Comentário"}
        widgets = {
            "nota": forms.NumberInput(attrs={"min": 0, "max": 20, "step": "0.5"}),
            "comentario": forms.Textarea(attrs={"rows": 4}),
        }
