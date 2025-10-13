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

# Cria um usuário não-root
RUN addgroup --system app && adduser --system --group app

# Instala dependências
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 cron nano libfreetype6 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia dependências pré-compiladas
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copia arquivos da aplicação
COPY . .

# Copia e configura o cron (como root)
COPY crontab /etc/cron.d/my-cron-jobs
RUN chmod 0644 /etc/cron.d/my-cron-jobs

# Copia e configura entrypoint (como root)
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Define o proprietário dos arquivos para o usuário não-root
RUN chown -R app:app /app

# Expõe a porta
EXPOSE 8000

# Define o entrypoint. O contêiner iniciará como ROOT para executar este script.
# A linha "USER app" foi removida daqui.
ENTRYPOINT ["/app/entrypoint.sh"]

# O comando padrão que o entrypoint irá executar como o usuário 'app'
CMD ["gunicorn", "crmspagi.wsgi:application", "--bind", "0.0.0.0:8000"]