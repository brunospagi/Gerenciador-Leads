#!/bin/sh

# Garante formato Unix no arquivo do cron quando o build vier de ambiente Windows
sed -i 's/\r$//' /etc/cron.d/my-cron-jobs 2>/dev/null || true
chmod 0644 /etc/cron.d/my-cron-jobs 2>/dev/null || true
touch /app/cron.log 2>/dev/null || true

# Inicia o cron em segundo plano e valida processo
cron
if pgrep cron >/dev/null 2>&1; then
  echo "Cron iniciado com sucesso."
else
  echo "Falha ao iniciar cron."
fi

# Aplica as migracoes do banco de dados
echo "Aplicando migracoes do banco de dados..."
python manage.py migrate --noinput

# Coleta os arquivos estaticos
echo "Coletando arquivos estaticos..."
python manage.py collectstatic --noinput --clear

# Sincronizacao inicial de contatos/labels/avatar para refletir fotos no boot
echo "Sincronizando labels/avatar do WhatsApp no boot..."
python manage.py check_whatsapp_labels --max-pages 10 || true

# Inicia o servidor Gunicorn (ou o comando passado do CMD do Dockerfile)
echo "Iniciando a aplicacao..."
exec "$@"
