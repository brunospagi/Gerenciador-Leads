# Usa uma imagem Python slim que já vem com ferramentas de build
FROM python:3.12-slim

# Define variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala as dependências do sistema necessárias
# - libpq-dev: para compilar o psycopg2
# - cron: para as tarefas agendadas
# - libfreetype6-dev: para a compilação do xhtml2pdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    cron \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia o arquivo de dependências
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia todos os arquivos do projeto para o diretório de trabalho
COPY . .

# Copia e configura o agendador de tarefas (cron)
COPY crontab /etc/cron.d/my-cron-jobs
RUN chmod 0644 /etc/cron.d/my-cron-jobs

# Copia e dá permissão de execução para o script de entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expõe a porta que o Gunicorn irá usar
EXPOSE 8000

# Define o entrypoint que será executado ao iniciar o contêiner
ENTRYPOINT ["/app/entrypoint.sh"]

# O comando padrão que o entrypoint irá executar no final
CMD ["gunicorn", "crmspagi.wsgi:application", "--bind", "0.0.0.0:8000"]