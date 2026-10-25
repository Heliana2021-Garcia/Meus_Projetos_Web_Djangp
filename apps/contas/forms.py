from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction

from apps.core.forms import EstiloCamposMixin
from apps.empresas.models import Empresa
from apps.estudantes.models import Curso, PerfilEstudante

from .models import Utilizador

# NIF de pessoa colectiva: 10 dígitos. Ajusta aqui se a regra for outra.
NIF_DIGITOS = 10


class EntrarForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nome de utilizador"
        self.fields["password"].label = "Palavra-passe"
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo"


class RegistoEstudanteForm(EstiloCamposMixin, UserCreationForm):
    numero_estudante = forms.CharField(label="Número de estudante", max_length=20)
    curso = forms.ModelChoiceField(
        label="Curso", queryset=Curso.objects.all(), empty_label="Seleccione o curso"
    )
    ano_frequencia = forms.TypedChoiceField(
        label="Ano de frequência",
        choices=[(i, f"{i}º ano") for i in range(1, 6)],
        coerce=int,
    )
    media_geral = forms.DecimalField(
        label="Média geral (0 a 20)",
        min_value=0,
        max_value=20,
        max_digits=4,
        decimal_places=2,
        localize=True,
    )

    field_order = [
        "first_name", "last_name", "numero_estudante", "curso", "ano_frequencia",
        "media_geral", "username", "email", "password1", "password2",
    ]

    class Meta(UserCreationForm.Meta):
        model = Utilizador
        fields = ("first_name", "last_name", "username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["first_name"].label = "Nome"
        self.fields["last_name"].label = "Apelido"

    def clean_numero_estudante(self):
        numero = self.cleaned_data["numero_estudante"].strip()
        if PerfilEstudante.objects.filter(numero_estudante=numero).exists():
            raise forms.ValidationError("Já existe um estudante com este número.")
        return numero

    @transaction.atomic
    def save(self, commit=True):
        utilizador = super().save(commit=False)
        utilizador.tipo = Utilizador.Tipo.ESTUDANTE
        utilizador.save()
        PerfilEstudante.objects.create(
            utilizador=utilizador,
            numero_estudante=self.cleaned_data["numero_estudante"],
            curso=self.cleaned_data["curso"],
            ano_frequencia=self.cleaned_data["ano_frequencia"],
            media_geral=self.cleaned_data["media_geral"],
        )
        return utilizador


class RegistoEmpresaForm(EstiloCamposMixin, UserCreationForm):
    nome_empresa = forms.CharField(label="Nome da empresa", max_length=150)
    nif = forms.CharField(
        label="NIF",
        max_length=20,
        help_text=f"{NIF_DIGITOS} dígitos. A administração valida o NIF antes de as vagas ficarem públicas.",
    )
    sector = forms.CharField(label="Sector de actividade", max_length=100, required=False)
    telefone = forms.CharField(label="Telefone", max_length=30, required=False)

    field_order = [
        "nome_empresa", "nif", "sector", "telefone", "first_name", "last_name",
        "username", "email", "password1", "password2",
    ]

    class Meta(UserCreationForm.Meta):
        model = Utilizador
        fields = ("first_name", "last_name", "username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["first_name"].label = "Nome do responsável"
        self.fields["last_name"].label = "Apelido do responsável"

    def clean_nif(self):
        nif = "".join(self.cleaned_data["nif"].split())
        if not nif.isdigit() or len(nif) != NIF_DIGITOS:
            raise forms.ValidationError(f"O NIF deve ter {NIF_DIGITOS} dígitos.")
        if Empresa.objects.filter(nif=nif).exists():
            raise forms.ValidationError("Já existe uma empresa registada com este NIF.")
        return nif

    @transaction.atomic
    def save(self, commit=True):
        utilizador = super().save(commit=False)
        utilizador.tipo = Utilizador.Tipo.EMPRESA
        utilizador.save()
        Empresa.objects.create(
            utilizador=utilizador,
            nome=self.cleaned_data["nome_empresa"],
            nif=self.cleaned_data["nif"],
            sector=self.cleaned_data["sector"],
            telefone=self.cleaned_data["telefone"],
        )
        return utilizador