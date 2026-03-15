# 02 - Arquitetura

## Stack

- Python + Django
- Templates server-side + Bootstrap
- PostgreSQL (producao)
- MinIO (arquivos)
- WhiteNoise (estaticos)
- OIDC opcional para SSO

## Estrutura de apps

- `crmspagi`: configuracao global e urls principais
- `core`: componentes base e contexto
- `usuarios`: perfis, dashboard admin, permissoes por modulo
- `clientes`, `distribuicao`, `vendas_produtos`, `financeiro`
- `financiamentos`, `controle_ponto`, `funcionarios`, `folha_pagamento`
- `documentos`, `autorizacoes`, `avaliacoes`, `credenciais`, `notificacoes`, `leadge`

## Fluxo macro

1. lead entra por clientes/distribuicao
2. vendedor atende e atualiza status
3. venda/servico e registrado
4. financeiro consolida receitas/despesas
5. relatorios apoiam decisao

## Camadas de acesso

- tela/menu (portal e sidebar)
- middleware por rota (`ModulePermissionMiddleware`)
- validacao em views (mixins/decorators)
