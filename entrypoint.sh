#!/bin/sh

# Inicia o serviço cron em segundo plano
cron

# Aplica as migrações do banco de dados
echo "Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

# Coleta os arquivos estáticos
echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

# Inicia o servidor Gunicorn (ou o comando passado para o Docker)
echo "Iniciando o servidor Gunicorn..."
exec "$@"