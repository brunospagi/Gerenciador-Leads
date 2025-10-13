# --- Estágio 1: Build ---
# Usa uma imagem Python slim para um tamanho final menor
FROM python:3.12-slim as builder

# Define o diretório de trabalho
WORKDIR /app

# Variáveis de ambiente para otimizar o build
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instala dependências do sistema necessárias para compilar pacotes Python
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev

# Instala o pip e as dependências
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# --- Estágio 2: Final ---
FROM python:3.12-slim

# Cria um usuário não-root para executar a aplicação
RUN addgroup --system app && adduser --system --group app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 cron nano && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia as dependências pré-compiladas do estágio de build
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copia os arquivos da aplicação
COPY . .

# Define o proprietário dos arquivos para o usuário não-root
RUN chown -R app:app /app

# Muda para o usuário não-root
USER app

# Copia e configura o agendador de tarefas (cron)
COPY crontab /etc/cron.d/my-cron-jobs
RUN chmod 0644 /etc/cron.d/my-cron-jobs

# Copia e dá permissão de execução para o script de entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expõe a porta que o Gunicorn irá usar
EXPOSE 8000

# Define o entrypoint e o comando padrão
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "crmspagi.wsgi:application", "--bind", "0.0.0.0:8000"]