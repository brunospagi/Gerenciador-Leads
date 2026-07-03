# Usa uma imagem Python slim que já vem com ferramentas de build
FROM python:3.12-slim

# Define variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala as dependências do sistema necessárias
# - libpq-dev: para compilar o psycopg2
# - cron: para as tarefas agendadas
# - libfreetype6-dev: para a compilação do xhtml2pdf
# - gosu: para o entrypoint largar privilegio de root antes de subir o gunicorn
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    cron \
    libfreetype6-dev \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Usuario nao-root que vai rodar o processo da aplicacao (gunicorn)
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /usr/sbin/nologin appuser

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
RUN sed -i 's/\r$//' /etc/cron.d/my-cron-jobs \
    && chmod 0644 /etc/cron.d/my-cron-jobs \
    && touch /app/cron.log \
    && chown appuser:appuser /app/cron.log

# Copia e dá permissão de execução para o script de entrypoint
# (sed remove eventual CRLF do arquivo, caso o build venha de um checkout Windows)
COPY entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Garante que a aplicacao (arquivos estaticos, staticfiles, etc) seja legivel/gravavel pelo appuser
RUN chown -R appuser:appuser /app

# Expõe a porta que o Gunicorn irá usar
EXPOSE 8000

# Define o entrypoint que será executado ao iniciar o contêiner
ENTRYPOINT ["/app/entrypoint.sh"]

# O comando padrão que o entrypoint irá executar no final
CMD ["gunicorn", "crmspagi.wsgi:application", "--bind", "0.0.0.0:8000"]
