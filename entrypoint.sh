#!/bin/sh

# Inicia o serviço cron (como root), o que agora funcionará.
echo "Iniciando o serviço cron..."
cron

# Aplica as migrações do banco de dados (como root)
echo "Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

# Coleta os arquivos estáticos (como root) e garante que o usuário 'app' seja o dono
echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput --clear
chown -R app:app /app/staticfiles

# Agora, executa o comando principal (passado do CMD do Dockerfile)
# como o usuário 'app', preservando os argumentos de forma segura.
echo "Iniciando a aplicação como usuário 'app'..."
exec su app -s /bin/sh -c 'exec "$@"' -- "$@"