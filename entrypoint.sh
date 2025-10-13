#!/bin/sh

# Inicia o serviço cron em segundo plano
crond -b

# Inicia o servidor Django (ou qualquer que seja o seu comando principal)
# Isso executa o comando passado como CMD no Dockerfile
exec "$@"