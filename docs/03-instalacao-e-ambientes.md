# 03 - Instalacao e Ambientes

## Requisitos

- Python 3.10+
- PostgreSQL
- (opcional) Docker

## Setup local (manual)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Setup com Docker

```bash
docker build -t crmspagi .
docker run -p 8000:8000 --env-file .env crmspagi
```

## Pos setup

- validar login
- validar menu por permissao
- validar pagina inicial (portal)
