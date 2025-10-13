# --- Estágio 1: Build ---
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev libfreetype6-dev

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# --- Estágio 2: Final ---
FROM python:3.12-slim

# Cria um usuário não-root para executar a aplicação
RUN addgroup --system app && adduser --system --group app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 cron nano libfreetype6 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia as dependências pré-compiladas do estágio de build
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copia os arquivos da aplicação
COPY . .

# >> CORREÇÃO: MOVEMOS A CONFIGURAÇÃO DO CRON PARA ANTES DE MUDAR DE USUÁRIO <<
# Copia e configura o agendador de tarefas (cron) enquanto ainda somos 'root'
COPY crontab /etc/cron.d/my-cron-jobs
RUN chmod 0644 /etc/cron.d/my-cron-jobs

# Copia o script de entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Define o proprietário dos arquivos da aplicação para o usuário não-root
RUN chown -R app:app /app

# >> AGORA SIM, MUDAMOS PARA O USUÁRIO NÃO-ROOT <<
USER app

# Expõe a porta que o Gunicorn irá usar
EXPOSE 8000

# Define o entrypoint e o comando padrão
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "crmspagi.wsgi:application", "--bind", "0.0.0.0:8000"]