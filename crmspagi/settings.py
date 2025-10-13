from pathlib import Path
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- CONFIGURAÇÕES DE PRODUÇÃO (LIDAS DO .ENV) ---
# A SECRET_KEY é lida do ambiente. Use uma chave forte em produção!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-default-key-for-dev')

# DEBUG é False em produção por padrão. Mude para 'True' no .env apenas para desenvolvimento.
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'

# Lê os hosts permitidos de uma variável de ambiente (separados por vírgula)
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

# O CSRF_TRUSTED_ORIGINS também deve ser configurado via variável de ambiente
CSRF_TRUSTED_ORIGINS = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', 'http://127.0.0.1,http://localhost').split(',')


# Configurações de sessão
SESSION_COOKIE_AGE = 43200
SESSION_SAVE_EVERY_REQUEST = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

# Diretórios adicionais para arquivos estáticos
STATICFILES_DIRS = [BASE_DIR / "static"]

# Configuração do WhiteNoise para servir arquivos estáticos em produção
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'leadge',
    'clientes',
    'avaliacoes',
    'minio_storage',
    'usuarios',
    'notificacoes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# --- Configurações do MinIO (LIDAS DO .ENV) ---
MINIO_EXTERNAL_ENDPOINT = os.getenv('MINIO_EXTERNAL_ENDPOINT', 's3.spagisistemas.com.br')
MINIO_STORAGE_ENDPOINT = os.getenv('MINIO_STORAGE_ENDPOINT', 's3.spagisistemas.com.br')
MINIO_STORAGE_ACCESS_KEY = os.getenv('MINIO_STORAGE_ACCESS_KEY')
MINIO_STORAGE_SECRET_KEY = os.getenv('MINIO_STORAGE_SECRET_KEY')
MINIO_STORAGE_USE_HTTPS = os.getenv('MINIO_STORAGE_USE_HTTPS', 'True') == 'True'
MINIO_STORAGE_MEDIA_BUCKET_NAME = os.getenv('MINIO_STORAGE_MEDIA_BUCKET_NAME', 'leads-spagi-media')
MINIO_STORAGE_AUTO_CREATE_MEDIA_BUCKET = True
DEFAULT_FILE_STORAGE = 'crmspagi.storage_backends.PublicMediaStorage'

ROOT_URLCONF = 'crmspagi.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notificacoes.context_processors.unread_notifications_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'crmspagi.wsgi.application'

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/contas/login/'
LOGIN_URL = '/contas/login/'

# --- Database (LIDO DO .ENV) ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "spagileads"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", "postgres"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# Password validation, Internationalization, etc.
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-BR'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'