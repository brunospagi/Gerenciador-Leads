from pathlib import Path
import os
from dotenv import load_dotenv

# Carrega as variÃ¡veis de ambiente do arquivo .env
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def _env_to_bool(name, default=False):
    value = os.getenv(name, str(default))
    return str(value).strip().lower() in {'1', 'true', 't', 'yes', 'y', 'on'}


def _env_to_int(name, default=0):
    value = os.getenv(name, str(default))
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _split_csv(value):
    return [item.strip() for item in str(value).split(',') if item.strip()]

# ConfiguraÃ§Ãµes do Webhook do Ponto (Lida do .ENV)
WEBHOOK_PONTO_URL = os.getenv('WEBHOOK_PONTO_URL')
EVOLUTION_API_URL = os.getenv('EVOLUTION_API_URL', '')
EVOLUTION_API_KEY = os.getenv('EVOLUTION_API_KEY', '')
EVOLUTION_INSTANCE = os.getenv('EVOLUTION_INSTANCE', '')
APP_BUILD_NUMBER = os.getenv('APP_BUILD_NUMBER', '0')
APP_BUILD_SHA = (
    os.getenv('APP_BUILD_SHA')
    or os.getenv('GITHUB_SHA')
    or os.getenv('RENDER_GIT_COMMIT')
    or ''
)
APP_BUILD_SHA_SHORT = APP_BUILD_SHA[:8] if APP_BUILD_SHA else ''

# --- CONFIGURAÃ‡Ã•ES DE PRODUÃ‡ÃƒO (LIDAS DO .ENV) ---
# A SECRET_KEY Ã© lida do ambiente. Use uma chave forte em produÃ§Ã£o!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-default-key-for-dev')

# DEBUG Ã© False em produÃ§Ã£o por padrÃ£o. Mude para 'True' no .env apenas para desenvolvimento.
DEBUG = _env_to_bool('DJANGO_DEBUG', False)

# LÃª os hosts permitidos de uma variÃ¡vel de ambiente (separados por vÃ­rgula)
ALLOWED_HOSTS = _split_csv(os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost'))

# O CSRF_TRUSTED_ORIGINS tambÃ©m deve ser configurado via variÃ¡vel de ambiente
CSRF_TRUSTED_ORIGINS = _split_csv(
    os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', 'http://127.0.0.1,http://localhost')
)

# Completa CSRF trusted origins com base em ALLOWED_HOSTS (evita falhas intermitentes em produÃ§Ã£o).
_csrf_from_env = [o.strip() for o in CSRF_TRUSTED_ORIGINS if o.strip()]
_csrf_dynamic = []
for host in [h.strip() for h in ALLOWED_HOSTS if h.strip()]:
    if host in ('*',):
        continue
    if '://' in host:
        _csrf_dynamic.append(host)
        continue
    if host.startswith('.'):
        wildcard_host = f"*.{host.lstrip('.')}"
        _csrf_dynamic.append(f"https://{wildcard_host}")
        _csrf_dynamic.append(f"http://{wildcard_host}")
        continue
    _csrf_dynamic.append(f"https://{host}")
    if host in ('127.0.0.1', 'localhost'):
        _csrf_dynamic.append(f"http://{host}")
CSRF_TRUSTED_ORIGINS = sorted(set(_csrf_from_env + _csrf_dynamic))

# ConfiguraÃ§Ãµes de sessÃ£o
SESSION_COOKIE_AGE = 43200
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'SAMEORIGIN'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
USE_X_FORWARDED_HOST = _env_to_bool('DJANGO_USE_X_FORWARDED_HOST', False)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = _env_to_bool('DJANGO_SECURE_SSL_REDIRECT', False)
SECURE_HSTS_SECONDS = _env_to_int('DJANGO_SECURE_HSTS_SECONDS', 0) if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_to_bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = _env_to_bool('DJANGO_SECURE_HSTS_PRELOAD', False)

CONTENT_SECURITY_POLICY = os.getenv(
    'DJANGO_CONTENT_SECURITY_POLICY',
    (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' https: wss:; "
        "frame-src 'self' https://www.youtube.com https://youtube.com; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self';"
    ),
)
CSRF_FAILURE_VIEW = 'crmspagi.views.csrf_failure'

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

# DiretÃ³rios adicionais para arquivos estÃ¡ticos
STATICFILES_DIRS = [BASE_DIR / "static"]

# ConfiguraÃ§Ã£o do WhiteNoise para servir arquivos estÃ¡ticos em produÃ§Ã£o
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'whitenoise.runserver_nostatic',
    'leadge',
    'clientes',
    'avaliacoes',
    'minio_storage',
    'usuarios',
    'notificacoes',
    'webpush',
    'documentos',
    'autorizacoes',
    'vendas_produtos',
    'financiamentos',
    'core',
    'mozilla_django_oidc',
    'distribuicao',
    'credenciais',
    'funcionarios',  
    'folha_pagamento',
    'financeiro',
    'controle_ponto',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.security_middleware.SecurityHeadersMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'usuarios.middleware.ModulePermissionMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

#--- ConfiguraÃ§Ã£o da API Gemini (LIDA DO .ENV) ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') 

# ConfiguraÃ§Ãµes do OIDC (Lidas do .ENV)
OIDC_RP_CLIENT_ID = os.getenv('OIDC_RP_CLIENT_ID')
OIDC_RP_CLIENT_SECRET = os.getenv('OIDC_RP_CLIENT_SECRET')
OIDC_RP_SIGN_ALGO = 'HS256' # Ou 'RS256', dependendo da config no Authentik

# Endpoints do Authentik (Substitua a URL base pela do seu Authentik)
# Exemplo: https://authentik.spagisistemas.com.br/application/o/<slug-da-aplicacao>/
OIDC_OP_AUTHORIZATION_ENDPOINT = os.getenv('OIDC_OP_AUTHORIZATION_ENDPOINT')
OIDC_OP_TOKEN_ENDPOINT = os.getenv('OIDC_OP_TOKEN_ENDPOINT')
OIDC_OP_USER_ENDPOINT = os.getenv('OIDC_OP_USER_ENDPOINT')

# --- ConfiguraÃ§Ã£o da API do Google Maps (NecessÃ¡ria para a API Weather) ---
# VocÃª precisa criar esta variÃ¡vel no seu .env para usar o weather.googleapis.com
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY') 

# --- ConfiguraÃ§Ãµes do MinIO (LIDAS DO .ENV) ---
MINIO_EXTERNAL_ENDPOINT = os.getenv('MINIO_EXTERNAL_ENDPOINT', 's3.spagisistemas.com.br')
MINIO_STORAGE_ENDPOINT = os.getenv('MINIO_STORAGE_ENDPOINT', 's3.spagisistemas.com.br')
MINIO_STORAGE_ACCESS_KEY = os.getenv('MINIO_STORAGE_ACCESS_KEY')
MINIO_STORAGE_SECRET_KEY = os.getenv('MINIO_STORAGE_SECRET_KEY')
MINIO_STORAGE_USE_HTTPS = os.getenv('MINIO_STORAGE_USE_HTTPS', 'True') == 'True'
MINIO_STORAGE_MEDIA_BUCKET_NAME = os.getenv('MINIO_STORAGE_MEDIA_BUCKET_NAME', 'leads-spagi-media')
MINIO_STORAGE_AUTO_CREATE_MEDIA_BUCKET = True
DEFAULT_FILE_STORAGE = 'crmspagi.storage_backends.PublicMediaStorage'

# --- ConfiguraÃ§Ãµes do django-webpush (LIDAS DO .ENV) ---
WEBPUSH_SETTINGS = {
    "VAPID_PUBLIC_KEY": os.getenv("VAPID_PUBLIC_KEY"),
    "VAPID_PRIVATE_KEY": os.getenv("VAPID_PRIVATE_KEY"),
    "VAPID_ADMIN_EMAIL": os.getenv("VAPID_ADMIN_EMAIL", "admin@example.com")
}

ROOT_URLCONF = 'crmspagi.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates', 
            BASE_DIR / 'crmspagi' / 'templates'
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notificacoes.context_processors.unread_notifications_context',
                'core.context_processors.banner_context',
                'core.context_processors.build_info_context',
                'usuarios.context_processors.module_access_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'crmspagi.wsgi.application'

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/contas/login/'
LOGIN_URL = '/contas/login/'



# --- Database (LIDO DO .ENV) ---
# DB_ENGINE aceitos: postgres | sqlite
DB_ENGINE = os.getenv("DB_ENGINE", "postgres").strip().lower()

if DB_ENGINE in {"sqlite", "sqlite3"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }
else:
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

# --- AutenticaÃ§Ã£o personalizada com OIDC ---

AUTHENTICATION_BACKENDS = [
    'crmspagi.oidc.SpagiOIDCBackend', 
    'django.contrib.auth.backends.ModelBackend',
]

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
USE_L10N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
