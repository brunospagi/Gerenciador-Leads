# 02 - Arquitetura

## Stack

- Backend: Python + Django
- Frontend: Django Templates + Bootstrap + JS
- Banco: PostgreSQL (producao) ou SQLite (local)
- Storage: MinIO (media), WhiteNoise (estaticos)
- Integracoes: WebPush, webhooks (n8n), OIDC opcional

## Estrutura de apps

- `crmspagi`: urls globais, views institucionais, dashboard executivo.
- `core`: componentes base, seguranca, auditoria, utilitarios transversais.
- `usuarios`: perfis, permissoes por modulo e administracao de usuarios.
- `clientes`: CRM de leads, pipeline comercial e relatorios.
- `distribuicao`: entrada/redistribuicao com regras de rodizio e disponibilidade.
- `vendas_produtos`: vendas, servicos, comissao e fechamento mensal.
- `financeiro`: transacoes e DRE.
- `funcionarios`, `controle_ponto`, `folha_pagamento`: ciclo de RH.
- `leadge`: TV corporativa e banners.
- Outros: `documentos`, `autorizacoes`, `avaliacoes`, `credenciais`, `notificacoes`, `financiamentos`.

## Fluxo macro

1. Lead entra em `distribuicao` (ou cadastro direto em `clientes`).
2. Lead e atribuido por rodizio para vendedor elegivel.
3. Vendedor evolui atendimento no pipeline comercial (`status_contato`, `etapa_funil`, andamento).
4. Conversao gera venda/servico em `vendas_produtos`.
5. Comissoes alimentam RH/folha e resultados operacionais.
6. Receitas/despesas consolidam o DRE no financeiro.
7. Auditoria e backup suportam governanca e continuidade.

## Camadas de acesso e seguranca

- Controle visual por menu/portal.
- `ModulePermissionMiddleware` bloqueando modulo nao autorizado.
- Regras por perfil em views (decorators/mixins).
- `SecurityHeadersMiddleware` para headers defensivos.
- `AuditLogMiddleware` registrando operacoes de escrita autenticadas.
