from django import forms


class EstiloCamposMixin:
    """Aplica as classes do Bootstrap aos campos e marca os que têm erro."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxSelectMultiple, forms.CheckboxInput)):
                classe = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                classe = "form-select"
            else:
                classe = "form-control"
            widget.attrs["class"] = (widget.attrs.get("class", "") + " " + classe).strip()

    def full_clean(self):
        super().full_clean()
        if self.is_bound:
            for nome in self.errors:
                if nome in self.fields:
                    widget = self.fields[nome].widget
                    widget.attrs["class"] = (widget.attrs.get("class", "") + " is-invalid").strip()