# 03 - Instalacao e Ambientes

## Requisitos

- Python 3.10+
- PostgreSQL (recomendado em producao)
- Docker (opcional)

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

- Validar login e logout.
- Validar menu por permissao de modulo.
- Validar painel de distribuicao, clientes e vendas.
- Validar dashboard executivo (`/painel-admin/`).

## Comandos relevantes

```bash
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
python manage.py gerar_backup_sistema
```
