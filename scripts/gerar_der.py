"""Gera docs/DER.md (diagrama Mermaid) a partir dos modelos reais do projecto.

Uso:  python manage.py shell -c "exec(open('scripts/gerar_der.py', encoding='utf-8').read())"
"""


def gerar():
    from pathlib import Path

    from django.apps import apps

    ignorar = {"admin", "auth", "contenttypes", "sessions", "messages", "staticfiles"}
    modelos = [m for m in apps.get_models() if m._meta.app_label not in ignorar]
    conhecidos = set(modelos)

    def nome(modelo):
        return f"{modelo._meta.app_label}_{modelo.__name__}"

    linhas, relacoes = ["erDiagram"], []
    for m in modelos:
        linhas.append(f"    {nome(m)} {{")
        for f in m._meta.concrete_fields:
            marca = " PK" if f.primary_key else (" FK" if f.is_relation else "")
            linhas.append(f"        {f.get_internal_type()} {f.name}{marca}")
        linhas.append("    }")
        for f in m._meta.concrete_fields:
            if f.is_relation and f.related_model in conhecidos:
                if f.one_to_one:
                    simbolo = "||--o|"
                else:
                    simbolo = "|o--o{" if f.null else "||--o{"
                relacoes.append(f'    {nome(f.related_model)} {simbolo} {nome(m)} : "{f.name}"')
        for f in m._meta.many_to_many:
            if f.related_model in conhecidos:
                relacoes.append(f'    {nome(m)} }}o--o{{ {nome(f.related_model)} : "{f.name}"')

    texto = (
        "# SIGEST - Diagrama Entidade-Relação\n\n"
        "Gerado automaticamente a partir dos modelos Django (`scripts/gerar_der.py`).\n"
        "Para ver o diagrama no VS Code, instale a extensão *Markdown Preview Mermaid Support*.\n\n"
        "```mermaid\n" + "\n".join(linhas + relacoes) + "\n```\n"
    )
    destino = Path("docs")
    destino.mkdir(exist_ok=True)
    (destino / "DER.md").write_text(texto, encoding="utf-8")
    print(f"OK docs/DER.md ({len(modelos)} entidades, {len(relacoes)} relações)")


gerar()