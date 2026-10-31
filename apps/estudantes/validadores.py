from django import forms

TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5 MB
EXTENSOES = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}


def validar_documento(ficheiro):
    """Confere extensão, tamanho e o início real do ficheiro (não só o nome)."""
    nome = ficheiro.name.lower()
    extensao = next((e for e in EXTENSOES if nome.endswith(e)), None)
    if extensao is None:
        raise forms.ValidationError("Formato não permitido. Envie PDF, PNG ou JPG.")
    if ficheiro.size > TAMANHO_MAXIMO:
        raise forms.ValidationError("O ficheiro não pode ter mais de 5 MB.")
    inicio = ficheiro.read(8)
    ficheiro.seek(0)
    if not any(inicio.startswith(m) for m in EXTENSOES[extensao]):
        raise forms.ValidationError("O conteúdo do ficheiro não corresponde ao formato indicado.")
    return ficheiro