# SIGEST

Gestão de estágios e inserção profissional - INSTIC / UniLuanda.

Stack: Django (MVT) + TailwindCSS 3.4 + SQLite (desenvolvimento) / PostgreSQL.

## Arranque

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements\dev.txt
Copy-Item .env.example .env        # preencher SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python scripts\criar_cursos.py
python scripts\criar_tecnologias.py
.\scripts\tailwindcss.exe -i static\src\input.css -o static\css\app.css --minify
python manage.py runserver
```

O executável do Tailwind (`scripts\tailwindcss.exe`) não vai para o Git: descarregar a versão 3.4.x para Windows.

## Testes

```powershell
python manage.py test
```

## PostgreSQL

Definir `DATABASE_URL` no `.env` e correr `python manage.py migrate`.