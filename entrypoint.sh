#!/bin/sh

# Inicia o serviço cron em segundo plano.
# O -L /dev/stdout envia os logs do cron para o log do Docker, facilitando a depuração.
cron -L /dev/stdout

# Aplica as migrações do banco de dados
echo "Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

# Coleta os arquivos estáticos
echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput --clear

# Inicia o servidor Gunicorn (ou o comando passado do CMD do Dockerfile)
echo "Iniciando a aplicação..."
exec "$@"