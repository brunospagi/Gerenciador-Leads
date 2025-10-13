# Use uma versão estável do Python (3.13 não existe ainda - use 3.12)
FROM python:3.12

# Cria o diretório da aplicação
RUN mkdir /app

# Define o diretório de trabalho
WORKDIR /app

# Recebe o valor do .env como argumento de build
ARG DJANGO_SUPERUSER_PASSWORD

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SUPERUSER_PASSWORD=$DJANGO_SUPERUSER_PASSWORD

# Atualiza o pip
RUN pip install --upgrade pip

RUN pip install psycopg

RUN pip install psycopg2
# Copia APENAS o requirements.txt primeiro (para cache de dependências)
COPY requirements.txt /app/

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

RUN python manage.py makemigrations clientes

# Copia TODOS os arquivos do projeto DEPOIS das dependências
COPY . /app/

# Expõe a porta do Django
EXPOSE 8000

# Inicia o servidor (APENAS para desenvolvimento)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
