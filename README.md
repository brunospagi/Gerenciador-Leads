# CRM Spagi - Gerenciador de Leads

Sistema CRM web focado no segmento automotivo, com controle de leads, distribuicao, vendas, financeiro, RH, documentos e permissoes por modulo.

## Documentacao Completa

A documentacao detalhada do projeto esta em:

- [docs/INDEX.md](./docs/INDEX.md)
- [README_EXECUTIVO.md](./README_EXECUTIVO.md)

## 1. Visao Geral

O projeto foi desenvolvido em Django e organiza o ciclo comercial completo:

- Entrada de lead
- Distribuicao automatica por rodizio
- Atendimento e historico do cliente
- Venda e servicos com comissao automatica
- Acompanhamento financeiro e DRE
- RH, ponto e folha
- Documentos e autorizacoes
- Permissoes por perfil e por modulo

## 2. Stack Tecnologica

- Backend: Python + Django
- Banco: PostgreSQL (producao) / SQLite (local opcional)
- Frontend: Django Templates + Bootstrap + JS
- Storage de arquivos: MinIO (django-minio-storage)
- Auth opcional: OIDC (mozilla-django-oidc)
- Deploy: Docker + Gunicorn + WhiteNoise
- PDF: xhtml2pdf
- Integracoes: requests, webpush, Gemini, Webhooks

## 3. Apps (Modulos)

- `clientes`: CRM de leads, calendario, atrasados, relatorios e PDF
- `distribuicao`: entrada/redistribuicao por rodizio e relatorio
- `vendas_produtos`: vendas e servicos, comissoes, fechamento mensal, relatorios
- `financeiro`: transacoes e DRE
- `financiamentos`: kanban de financiamentos
- `controle_ponto`: registro de ponto, mapa e auditoria
- `folha_pagamento`: lancamentos e folha
- `funcionarios`: cadastro de equipe
- `documentos`: procuracoes e outorgados
- `autorizacoes`: solicitacoes e aprovacao
- `avaliacoes`: avaliacoes e gerador de anuncios
- `credenciais`: gestao de acessos/senhas internas
- `usuarios`: perfis, dashboard admin, permissoes por modulo
- `notificacoes`: alertas e comandos agendados
- `leadge`: banners e recursos visuais
- `core` e `crmspagi`: base do projeto, urls e configuracoes

## 4. Permissoes e Seguranca

O sistema usa duas camadas:

1. Perfil do usuario (`nivel_acesso`: ADMIN, GERENTE, VENDEDOR, etc.)
2. Permissao por modulo (`ModulePermission`)

Implementacoes recentes:

- Middleware: `usuarios.middleware.ModulePermissionMiddleware`
- Regras centrais: `usuarios.permissions.has_module_access`
- Gestao via tela: `Usuarios -> Permissoes por Modulo`
- Sidebar e portal exibem apenas modulos permitidos

## 5. Campo Novo em Vendas

Foi adicionado o campo `origem_cliente` em `VendaProduto` com opcoes:

- Indicacao
- Instagram
- Facebook
- OLX
- Site
- Passagem na Loja
- WhatsApp
- Outro

Arquivos relacionados:

- `vendas_produtos/models.py`
- `vendas_produtos/forms.py`
- `vendas_produtos/templates/vendas_produtos/form.html`
- `vendas_produtos/migrations/0016_vendaproduto_origem_cliente.py`

## 6. Requisitos

- Python 3.10+
- PostgreSQL (recomendado)
- Docker (opcional, recomendado para producao)

Dependencias principais estao em `requirements.txt`.

## 7. Configuracao de Ambiente

Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

Variaveis principais:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `MINIO_*`
- `OIDC_*` (se usar login SSO)
- `VAPID_*` (webpush)
- `N8N_WEBHOOK_URL`, `WEBHOOK_PONTO_URL`
- `GEMINI_API_KEY`

## 8. Rodando Localmente

### Opcao A: ambiente Python

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

### Opcao B: Docker

```bash
docker build -t crmspagi .
docker run -p 8000:8000 --env-file .env crmspagi
```

## 9. Comandos Uteis

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py test
```

Comandos de notificacao (usados no cron):

```bash
python manage.py check_inactivity
python manage.py check_overdue_clients
```

## 10. Jobs Agendados (Cron)

Arquivo: `crontab`

- `check_inactivity`: diariamente 03:00
- `check_overdue_clients`: diariamente 08:00

## 11. Estrutura de Deploy

O `entrypoint.sh` faz:

1. sobe cron
2. roda migracoes
3. roda collectstatic
4. inicia o processo principal (Gunicorn)

## 12. Observacoes Adicionais (Importantes)

- Sempre rode `migrate` apos atualizar o codigo.
- Ha migracoes novas de permissao/modulo e origem de cliente em vendas.
- Em ambientes Windows pode haver variacao de final de linha (CRLF/LF); isso nao afeta execucao do Django.
- Validar permissao por modulo apos criar novos usuarios.
- Para producao, revise `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, MinIO e OIDC.

## 13. Checklist de Pos-Atualizacao

1. `python manage.py migrate`
2. Validar login de ADMIN e perfil comum
3. Conferir cards e menu lateral por modulo
4. Testar cadastro de venda com `origem_cliente`
5. Testar impressao do relatorio de distribuicao

## 14. Melhorias Recomendadas

- Adicionar testes automatizados para regras de permissao por modulo
- Criar dashboards de conversao por origem do lead
- Adicionar exportacao CSV/XLS para relatorios principais
- Padronizar auditoria de alteracoes em entidades criticas

---

Se quiser, eu tambem posso gerar uma versao do README com diagrama de arquitetura (fluxo lead -> distribuicao -> venda -> financeiro) e um guia de onboarding para novos usuarios (vendedor, gerente e admin).
