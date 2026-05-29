# 07 - Rotas Principais

## Raiz (`crmspagi/urls.py`)

- `/` portal
- `/painel-admin/` dashboard executivo
- `/painel-admin/backup/` gerar backup (POST)
- `/painel-admin/logs-auditoria/` consulta de auditoria
- `/clientes/`, `/vendas/`, `/financeiro/`, `/distribuicao/`, `/ponto/`, `/rh/`, `/funcionarios/`
- `/documentos/`, `/autorizacoes/`, `/financiamentos/`, `/acessos/`

## Clientes (`/clientes/`)

- `/clientes/` lista principal
- `/clientes/pipeline-comercial/` kanban comercial
- `/clientes/calendario/`
- `/clientes/cliente/novo/`
- `/clientes/cliente/<pk>/`
- `/clientes/cliente/<pk>/editar/`
- `/clientes/cliente/<pk>/registrar_andamento/`
- `/clientes/relatorios/`

## Distribuicao (`/distribuicao/`)

- `/distribuicao/entrada/`
- `/distribuicao/relatorio/`
- `/distribuicao/redistribuir/<pk>/`

## Vendas (`/vendas/`)

- `/vendas/`
- `/vendas/novo/`
- `/vendas/relatorio/`
- `/vendas/<pk>/aprovar/`
- `/vendas/<pk>/rejeitar/`
- `/vendas/<pk>/minuta/`
- `/vendas/fechamento/`
- `/vendas/configuracao/comissao/`

## Financeiro (`/financeiro/`)

- `/financeiro/`
- `/financeiro/nova/`
- `/financeiro/<pk>/editar/`
- `/financeiro/relatorio/`

## Ponto (`/ponto/`)

- `/ponto/`
- `/ponto/mapa/`
- `/ponto/relatorio/`
- `/ponto/homologacao/`
- `/ponto/pendencias/modal/`

## RH (`/rh/`)

- `/rh/`
- `/rh/folha/<pk>/`
- `/rh/desconto/novo/`
- `/rh/credito/novo/`
- `/rh/lancamentos/lista/`

## TV e banners (`leadge`)

- `/tv-video/`
- `/tv/gestao/`
- `/tv/gestao/programacao/nova/`
- `/banners/`
