from django import forms

from apps.core.forms import EstiloCamposMixin

from .models import Avaliacao


class AvaliacaoForm(EstiloCamposMixin, forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = [nome for nome, _ in Avaliacao.CRITERIOS] + ["comentario"]
        widgets = {
            **{
                nome: forms.NumberInput(attrs={"min": 0, "max": 20, "step": "0.5"})
                for nome, _ in Avaliacao.CRITERIOS
            },
            "comentario": forms.Textarea(attrs={"rows": 3}),
        }