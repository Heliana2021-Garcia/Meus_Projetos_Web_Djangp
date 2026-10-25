from django import forms


class EstiloCamposMixin:
    """Aplica a classe CSS `campo` a todos os campos (excepto caixas de selecção)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if not isinstance(campo.widget, forms.CheckboxSelectMultiple):
                campo.widget.attrs["class"] = "campo"