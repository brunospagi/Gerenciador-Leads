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

## 5. Novidades em Vendas

Foi adicionado o campo `origem_cliente` em `VendaProduto` com opcoes:

- Indicacao
- Instagram
- Facebook
- OLX
- Site
- Passagem na Loja
- WhatsApp
- Outro

Tambem foi adicionada a impressao de `MINUTA` no fluxo de aprovacao:

- Ao aprovar uma venda, o sistema redireciona para a minuta com impressao automatica
- A minuta possui logo, rodape com horario e usuario que gerou
- A minuta inclui campos de cadastro do cliente/veiculo para preenchimento completo
- Bloco final com marcacao manual: `CONSIGNADO ( )` e `PROPRIO ( )`

Campos novos no modelo `VendaProduto` para suportar a minuta:

- `dtnasc_cliente`, `rgIE_cliente`, `telCel_cliente`, `cpfCNPJ_cliente`
- `endereco_cliente`, `numero_cliente`, `cep_cliente`, `bairro_cliente`, `cidade_com_cliente`
- `marca_veiculo`, `km_veiculo`, `data_compra`, `documentacao_veiculo`

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
- `DJANGO_SECURE_SSL_REDIRECT`
- `DJANGO_USE_X_FORWARDED_HOST`
- `DJANGO_SECURE_HSTS_SECONDS`
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`
- `DJANGO_SECURE_HSTS_PRELOAD`
- `DJANGO_CONTENT_SECURITY_POLICY` (opcional para override)
- `APP_BUILD_NUMBER` (numero da build exibido no rodape)
- `APP_BUILD_SHA` (hash curto/commit exibido no rodape)
- `DB_ENGINE` (`postgres` ou `sqlite`)
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` (quando `DB_ENGINE=postgres`)
- `SQLITE_PATH` (quando `DB_ENGINE=sqlite`)
- `MINIO_*`
- `OIDC_*` (se usar login SSO)
- `VAPID_*` (webpush)
- `N8N_WEBHOOK_URL`, `WEBHOOK_PONTO_URL`
- `GEMINI_API_KEY`

Observacoes importantes:

- `.env.example` foi sanitizado com valores ficticios (somente modelo)
- `DJANGO_DEBUG` agora e interpretado corretamente como booleano (`True`/`False`)
- o rodape exibe build via `APP_BUILD_NUMBER` e `APP_BUILD_SHA` (ou `GITHUB_SHA`/`RENDER_GIT_COMMIT` como fallback)
- headers de seguranca foram reforcados (CSP, Referrer-Policy, nosniff e Permissions-Policy)
- endpoints webpush usam CSRF normal com envio automatico de `X-CSRFToken` no frontend

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

Comando de backup do sistema:

```bash
python manage.py gerar_backup_sistema
# opcional: definir pasta de saida
python manage.py gerar_backup_sistema --output-dir /caminho/para/backups
```

O backup tambem pode ser gerado no painel executivo (`/painel-admin/`) pelo botao
`Baixar Backup (.zip)`.

Auditoria de acoes administrativas:

- Tela no painel: `/painel-admin/logs-auditoria/` (somente ADMIN/superuser)
- Registros automaticos de requisicoes de escrita (`POST`, `PUT`, `PATCH`, `DELETE`)
- Filtros por usuario, modulo, metodo, severidade, resultado e periodo

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

## 14. Controle de Ponto (Novas Rotinas)

- Nova tela de homologacao por colaborador:
  - URL: `/ponto/homologacao/`
  - Permite aprovacao manual por registro
  - Permite aprovacao/recusa em lote (selecionados)
  - Filtro por colaborador, mes e ano
- Fechamento da folha ponto por colaborador e mes:
  - Acao via modal dentro da homologacao
  - Bloqueia novas batidas no relogio para o mes fechado
  - Reabertura manual pelo administrador/gerente
- Pendencias automaticas para homologacao:
  - Entradas com atraso acima da tolerancia ficam pendentes
  - Entradas com validacao manual (`manual_*`) ficam pendentes
- Alerta para administracao:
  - Ao entrar no sistema, admin/gerente recebe modal se houver pendencias
  - Link direto para a tela de homologacao

## 15. UX de Suporte (WhatsApp)

- Botao flutuante de suporte no canto inferior quando estiver em rotas com `whatsapp`:
  - Telefone: `+55 41 99924-8121`
  - Link: `https://wa.me/5541999248121`

## 14. Melhorias Recomendadas

- Adicionar testes automatizados para regras de permissao por modulo
- Criar dashboards de conversao por origem do lead
- Adicionar exportacao CSV/XLS para relatorios principais
- Padronizar auditoria de alteracoes em entidades criticas

## 15. Design System (M3)

Foi padronizado um design system inspirado em Material 3 para toda a aplicacao:

- CSS global em `static/css/app_m3.css`
- UX global em `static/js/app_ux.js`
- Bases principais atualizadas:
  - `crmspagi/templates/base_portal.html`
  - `clientes/templates/base.html`
  - `avaliacoes/templates/base.html`

Recursos ativos globalmente:

- Barra de progresso e mascara de carregamento em navegacao e requisicoes `fetch`
- Feedback de envio de formularios com botao em estado `Enviando...`
- Validacao visual de campos obrigatorios e invalidos
- Auto-dismiss de alertas
- Mascaras utilitarias (`money-mask`, `cpf-mask`, `cep-mask`, `phone-mask`)

Observacao sobre NPM/Docker:

- Nesta etapa nao foi necessario pipeline npm para aplicar o M3 (assets servidos via `static` do Django).
- O Docker atual continua valido sem alteracao obrigatoria para frontend build.

## 16. QA Funcional (Fluxos Criticos)

Execute este roteiro antes de cada deploy:

1. Vendas
- Criar venda com e sem adicionais.
- Editar venda pendente.
- Aprovar venda como GERENTE (sem alterar custo) e como ADMIN (alterando custo).
- Reprovar venda com motivo.
- Validar impressao de comprovante e minuta.
- Validar ajuste de custo apos aprovacao (somente ADMIN).

2. Ponto
- Registrar entrada dentro da tolerancia.
- Registrar entrada com atraso e justificativa.
- Validar que a foto capturada no ponto atualiza automaticamente o avatar do usuario.
- Homologar ocorrencia (aceitar/recusar) em `Ocorrencias de Ponto`.
- Validar `Espelho de Ponto Mensal` e `Relatorio de Entradas`.
- Validar impressao A4 (portrait/landscape conforme tela).

3. RH/Folha
- Atualizar referencia do mes.
- Fechar mes e marcar pagamento do mes.
- Abrir detalhe da folha e validar conferencia de comissoes.
- Validar permissao: ADMIN x colaborador.

4. Financeiro
- Criar lancamento receita/despesa.
- Executar acao em lote (pendente/efetivado).
- Validar DRE por mes.
- Garantir que nao-admin so veja seus proprios lancamentos.

## 17. Checklist de Deploy e Seguranca

1. `python manage.py migrate`
2. `python manage.py collectstatic --noinput`
3. `python manage.py check`
4. Validar login e menu por perfil (ADMIN, GERENTE, VENDEDOR, RH)
5. Validar cookies/headers de seguranca (`CSP`, `Referrer-Policy`, `nosniff`)
6. Validar CSRF em formularios e `fetch` com `X-CSRFToken`
7. Validar build no rodape (`APP_BUILD_NUMBER` / `APP_BUILD_SHA`)
8. Validar impressao A4 dos relatorios operacionais
9. Revisar logs de erro apos subir
10. Confirmar backup do banco antes de release critica

---

Se quiser, eu tambem posso gerar uma versao do README com diagrama de arquitetura (fluxo lead -> distribuicao -> venda -> financeiro) e um guia de onboarding para novos usuarios (vendedor, gerente e admin).
