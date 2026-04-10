# 04 - Configuracao de Ambiente (.env)

## Variaveis principais

- Django
  - `DJANGO_SECRET_KEY`
  - `DJANGO_DEBUG`
  - `DJANGO_ALLOWED_HOSTS`
  - `DJANGO_CSRF_TRUSTED_ORIGINS`

- Banco
  - `DB_ENGINE` (`postgres` ou `sqlite`)
  - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` (quando `DB_ENGINE=postgres`)
  - `SQLITE_PATH` (quando `DB_ENGINE=sqlite`)

- Storage MinIO
  - `MINIO_EXTERNAL_ENDPOINT`
  - `MINIO_STORAGE_ENDPOINT`
  - `MINIO_STORAGE_ACCESS_KEY`
  - `MINIO_STORAGE_SECRET_KEY`
  - `MINIO_STORAGE_USE_HTTPS`
  - `MINIO_STORAGE_MEDIA_BUCKET_NAME`

- Integracoes
  - `GEMINI_API_KEY`
  - `GOOGLE_MAPS_API_KEY`
  - `N8N_WEBHOOK_URL`
  - `WEBHOOK_PONTO_URL`

- OIDC (opcional)
  - `OIDC_RP_CLIENT_ID`
  - `OIDC_RP_CLIENT_SECRET`
  - `OIDC_OP_AUTHORIZATION_ENDPOINT`
  - `OIDC_OP_TOKEN_ENDPOINT`
  - `OIDC_OP_USER_ENDPOINT`

- Webpush
  - `VAPID_PUBLIC_KEY`
  - `VAPID_PRIVATE_KEY`
  - `VAPID_ADMIN_EMAIL`

## Observacao

Garanta que os valores de producao nao sejam versionados.

O arquivo `.env.example` contem somente valores ficticios e deve ser usado como base.

Exemplo rapido:

```env
# PostgreSQL
DB_ENGINE=postgres
DB_NAME=app_exemplo
DB_USER=app_user
DB_PASSWORD=senha_ficticia_123
DB_HOST=postgres
DB_PORT=5432

# SQLite
# DB_ENGINE=sqlite
# SQLITE_PATH=db.sqlite3
```
