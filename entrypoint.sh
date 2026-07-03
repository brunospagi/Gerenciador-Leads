#!/bin/sh
set -e

# Controla se este container deve rodar o cron interno (check_inactivity, check_overdue_clients).
# Default "true" preserva o comportamento atual. Se a aplicacao for escalada com multiplas
# replicas, defina ENABLE_CRON=false em todas menos uma, para nao duplicar os jobs agendados
# (e as notificacoes que eles disparam) em cada replica.
ENABLE_CRON="${ENABLE_CRON:-true}"

if [ "$ENABLE_CRON" = "true" ]; then
  # Garante formato Unix no arquivo do cron quando o build vier de ambiente Windows
  sed -i 's/\r$//' /etc/cron.d/my-cron-jobs 2>/dev/null || true
  chmod 0644 /etc/cron.d/my-cron-jobs 2>/dev/null || true
  touch /app/cron.log 2>/dev/null || true

  # Inicia o cron em segundo plano e valida processo.
  # Usa /proc diretamente (nao depende de pgrep/ps, ausentes na imagem slim).
  cron >/dev/null 2>&1 || true
  CRON_OK=0
  for comm_file in /proc/[0-9]*/comm; do
    if [ -r "$comm_file" ] && grep -qx 'cron\|crond' "$comm_file" 2>/dev/null; then
      CRON_OK=1
      break
    fi
  done
  if [ "$CRON_OK" -eq 1 ]; then
    echo "Cron iniciado com sucesso."
  else
    echo "Falha ao iniciar cron."
  fi
else
  echo "ENABLE_CRON=false: pulando inicializacao do cron neste container."
fi

# Aplica as migracoes do banco de dados
echo "Aplicando migracoes do banco de dados..."
python manage.py migrate --noinput

# Coleta os arquivos estaticos
echo "Coletando arquivos estaticos..."
python manage.py collectstatic --noinput --clear

# Inicia o servidor Gunicorn (ou o comando passado do CMD do Dockerfile) sem privilegio de root.
# O cron (acima) continua rodando como root, ja que os jobs em /etc/cron.d exigem isso.
echo "Iniciando a aplicacao..."
exec gosu appuser "$@"
