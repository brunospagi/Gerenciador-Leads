# CRM Spagi - Gerenciador de Leads

Sistema CRM web focado no segmento automotivo, com controle de leads, distribuição, vendas, financeiro, RH, documentos e permissões por módulo.

## Documentação Completa

- [docs/INDEX.md](./docs/INDEX.md) - documentação técnica detalhada, por assunto
- [README_EXECUTIVO.md](./README_EXECUTIVO.md) - resumo para gestão/diretoria

## 1. Visão Geral

O projeto é desenvolvido em Django e organiza o ciclo comercial completo:

- Entrada de lead e distribuição automática por rodízio
- Atendimento com pipeline comercial (etapa, status de contato, timeline de andamento)
- Venda e serviços com comissão automática
- Acompanhamento financeiro e DRE
- RH, ponto e folha de pagamento
- Documentos e autorizações
- Permissões por perfil e por módulo, com trilha de auditoria

## 2. Stack Tecnológica

- **Backend**: Python + Django 5.2 (requer Python 3.10+)
- **Banco**: PostgreSQL (produção) / SQLite (local opcional)
- **Frontend**: Django Templates + Bootstrap 5 + JS (design system M3 em `static/css/app_m3.css` e `static/js/app_ux.js`)
- **Storage de arquivos**: MinIO (`django-minio-storage`)
- **Auth opcional**: OIDC (`mozilla-django-oidc`)
- **Deploy**: Docker (usuário não-root) + Gunicorn + WhiteNoise + cron
- **PDF**: xhtml2pdf
- **Integrações**: requests, webpush, Gemini, Evo CRM, webhooks (n8n)

## 3. Apps (Módulos)

- `clientes`: CRM de leads, calendário, atrasados, relatórios e PDF
- `distribuicao`: entrada/redistribuição por rodízio, checagem de duplicidade ao vivo e relatório
- `vendas_produtos`: vendas e serviços, comissões, fechamento mensal, relatórios
- `financeiro`: transações e DRE
- `financiamentos`: kanban de financiamentos
- `controle_ponto`: registro de ponto, homologação e auditoria
- `folha_pagamento`: lançamentos e folha
- `funcionarios`: cadastro de equipe
- `documentos`: procurações e outorgados
- `autorizacoes`: solicitações e aprovação
- `avaliacoes`: avaliações de veículo e gerador de anúncios
- `credenciais`: gestão de acessos/senhas internas
- `usuarios`: perfis, dashboard admin, permissões por módulo
- `notificacoes`: alertas, push (webpush) e comandos agendados
- `leadge`: TV corporativa, banners e recursos visuais
- `core` e `crmspagi`: base do projeto, urls, middlewares e configurações

## 4. Permissões e Segurança

O sistema usa duas camadas:

1. Perfil do usuário (`nivel_acesso`: ADMIN, GERENTE, VENDEDOR, etc.)
2. Permissão por módulo (`ModulePermission`)

Pontos principais:

- Middleware: `usuarios.middleware.ModulePermissionMiddleware`
- Regra central: `usuarios.permissions.has_module_access` (sem registro de `ModulePermission`, o acesso é negado por padrão em vez de liberado)
- Gestão via tela: `Usuários -> Permissões por Módulo`
- Sidebar e portal exibem apenas os módulos permitidos ao usuário logado
- Trilha de auditoria de operações de escrita em `/painel-admin/logs-auditoria/`

Veja detalhes em [docs/05-permissoes-e-seguranca.md](./docs/05-permissoes-e-seguranca.md).

## 5. Requisitos

- Python 3.10+ (o Django 5.2 não roda em versões anteriores)
- PostgreSQL (recomendado em produção) ou SQLite (local)
- Docker (opcional, recomendado para produção)

Dependências e versões estão fixadas em `requirements.txt`.

## 6. Configuração de Ambiente

Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

Variáveis principais:

| Variável | Uso |
| --- | --- |
| `DJANGO_SECRET_KEY` | chave secreta do Django |
| `DJANGO_DEBUG` | `True`/`False` |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | hosts e origens confiáveis |
| `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_USE_X_FORWARDED_HOST` | proxy/HTTPS |
| `DJANGO_SECURE_HSTS_SECONDS`, `..._INCLUDE_SUBDOMAINS`, `..._PRELOAD` | HSTS |
| `DJANGO_CONTENT_SECURITY_POLICY` | override opcional da CSP padrão |
| `APP_BUILD_NUMBER`, `APP_BUILD_SHA` | build exibida no rodapé |
| `ENABLE_CRON` | controla se este container roda o cron interno (ver seção 9) |
| `DB_ENGINE` | `postgres` ou `sqlite` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | quando `DB_ENGINE=postgres` |
| `SQLITE_PATH` | quando `DB_ENGINE=sqlite` |
| `MINIO_*` | storage de arquivos |
| `OIDC_*` | login SSO (opcional) |
| `VAPID_*` | webpush |
| `N8N_WEBHOOK_URL`, `WEBHOOK_PONTO_URL` | webhooks |
| `GEMINI_API_KEY` | integrações de IA (avaliações, extração de documentos) |

Observações importantes:

- `.env.example` contém apenas valores fictícios (modelo).
- O rodapé exibe a build via `APP_BUILD_NUMBER`/`APP_BUILD_SHA` (ou `GITHUB_SHA`/`RENDER_GIT_COMMIT` como fallback).
- Headers de segurança reforçados: CSP, Referrer-Policy, `nosniff` e Permissions-Policy.
- Endpoints webpush usam CSRF normal com envio automático de `X-CSRFToken` no frontend.
- Arquivos de shell/config (`*.sh`, `crontab`, `Dockerfile`) têm quebra de linha forçada para LF via `.gitattributes` — evita builds Docker quebrados quando o checkout é feito no Windows.

## 7. Rodando Localmente

### Opção A: ambiente Python

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Opção B: Docker

```bash
docker build -t crmspagi .
docker run -p 8000:8000 --env-file .env crmspagi
```

O container roda a aplicação (Gunicorn) com um usuário não-root; o cron interno continua rodando como root (necessário para `/etc/cron.d`).

## 8. Comandos Úteis

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py test
```

Comandos de notificação e reconciliação (usados no cron/rotina):

```bash
python manage.py check_inactivity
python manage.py check_overdue_clients
python manage.py sincronizar_evo_crm          # reprocessa leads recentes sem sincronizar com o Evo CRM
```

Comando de backup do sistema:

```bash
python manage.py gerar_backup_sistema
# opcional: definir pasta de saida
python manage.py gerar_backup_sistema --output-dir /caminho/para/backups
```

O backup também pode ser gerado no painel executivo (`/painel-admin/`) pelo botão `Baixar Backup (.zip)`.

## 9. Testes e CI

```bash
python manage.py test
```

O pipeline de CI (`.github/workflows/django.yml`) roda em Python 3.12 com SQLite e executa a suíte completa a cada push/PR para `main`. Cobertura automatizada inclui: distribuição (rodízio, deduplicação, integração Evo CRM), permissões por módulo, upload de documentos/biometria, comissões de venda, DRE financeiro e pipeline de clientes.

## 10. Jobs Agendados (Cron)

Arquivo: `crontab`

- `check_inactivity`: diariamente às 03:00
- `check_overdue_clients`: diariamente às 08:00

O cron roda dentro do próprio container web, controlado pela variável `ENABLE_CRON` (default `true`). **Se a aplicação escalar com múltiplas réplicas, defina `ENABLE_CRON=false` em todas menos uma** — caso contrário cada réplica roda seu próprio cron e os jobs (e notificações que eles disparam) executam duplicados.

## 11. Estrutura de Deploy

O `entrypoint.sh` faz, nesta ordem:

1. Sobe o cron (se `ENABLE_CRON=true`)
2. Roda migrações (`migrate`)
3. Roda `collectstatic`
4. Troca para o usuário não-root e inicia o processo principal (Gunicorn), via `gosu`

## 12. Checklist de Deploy e Segurança

1. `python manage.py migrate`
2. `python manage.py collectstatic --noinput`
3. `python manage.py check`
4. `python manage.py test`
5. Validar login e menu por perfil (ADMIN, GERENTE, VENDEDOR, RH)
6. Validar cookies/headers de segurança (CSP, Referrer-Policy, `nosniff`)
7. Validar CSRF em formulários e `fetch` com `X-CSRFToken`
8. Validar build no rodapé (`APP_BUILD_NUMBER`/`APP_BUILD_SHA`)
9. Revisar logs de erro após subir
10. **Fazer backup do banco antes de qualquer release com migration nova** (ver `python manage.py gerar_backup_sistema`)

## 13. QA Funcional (Fluxos Críticos)

Execute este roteiro antes de cada deploy relevante:

**Vendas**
- Criar venda com e sem adicionais; editar venda pendente.
- Aprovar venda como GERENTE (sem alterar custo) e como ADMIN (alterando custo); reprovar com motivo.
- Validar impressão de comprovante e minuta.

**Ponto**
- Registrar entrada dentro/fora da tolerância (com justificativa).
- Validar que a foto capturada atualiza o avatar do usuário.
- Homologar ocorrência (aceitar/recusar) e validar espelho de ponto mensal.

**RH/Folha**
- Atualizar referência do mês, fechar mês e marcar pagamento.
- Abrir detalhe da folha e validar conferência de comissões.
- Validar permissão: ADMIN x colaborador.

**Financeiro**
- Criar lançamento receita/despesa; executar ação em lote (pendente/efetivado).
- Validar DRE por mês.
- Garantir que não-admin só veja seus próprios lançamentos.

**Distribuição**
- Cadastrar lead com telefone já existente e confirmar aviso de duplicidade ao vivo (sem reload).
- Redistribuir lead e validar rodízio.

## 14. Recursos de UX

- Design system inspirado em Material 3 (`static/css/app_m3.css`, `static/js/app_ux.js`): barra de progresso em navegação/`fetch`, feedback de envio (`Enviando...`), validação visual de campos obrigatórios/inválidos, auto-dismiss de alertas, máscaras utilitárias (`money-mask`, `cpf-mask`, `cep-mask`, `phone-mask`).
- Service Worker/push notifications registrados a partir do layout principal (`clientes/templates/base.html`), com suporte a cadastro de cliente offline (sincronização automática ao reconectar).
- Botão flutuante de suporte via WhatsApp em rotas relevantes (`+55 41 99924-8121`).

## 15. Melhorias Recomendadas

- Dashboards de conversão por origem do lead e SLA de follow-up
- Exportação CSV/XLS para relatórios principais
- Observabilidade centralizada (APM, logs estruturados, alertas de exceção)
- Ampliar cobertura de testes para folha de pagamento, controle de ponto e financiamentos
