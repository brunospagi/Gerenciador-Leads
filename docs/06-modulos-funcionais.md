# 06 - Modulos Funcionais

## Clientes (`clientes`)

- Cadastro e manutencao de leads.
- Lista de ativos, atrasados e finalizados.
- Pipeline comercial com funil (`etapa_funil`) e status de contato (`status_contato`).
- Timeline de andamento (`LeadAndamento`) com comentario e proxima acao.
- Relatorios e exportacao PDF.

## Distribuicao (`distribuicao`)

- Entrada de lead com validacao de duplicidade por WhatsApp.
- Rodizio de vendedores com regras de disponibilidade por ponto/almoco.
- Redistribuicao manual com historico.
- Relatorio diario/semanal/mensal com impressao.

## Vendas (`vendas_produtos`)

- Cadastro de venda de veiculo/moto e servicos.
- Fluxo de aprovacao/rejeicao.
- Minuta e comprovante de impressao.
- Comissao com split de ajudante.
- Regra de comissao de gerencia (exclui vendas em nome de admin/gerente).
- Fechamento mensal de vendas.

## Financeiro (`financeiro`)

- Receitas e despesas.
- Transacoes recorrentes.
- Relatorio DRE mensal.

## RH (`funcionarios`, `controle_ponto`, `folha_pagamento`)

- Cadastro de colaboradores.
- Registro de ponto com homologacao e relatorios.
- Folha com creditos/descontos.
- Holerite com detalhamento completo de comissao e hash de integridade no rodape.

## Administracao executiva (`crmspagi` + `core`)

- Dashboard executivo (`/painel-admin/`).
- Backup completo por botao e comando `gerar_backup_sistema`.
- Logs de auditoria com filtros.

## Midia corporativa (`leadge`)

- TV corporativa com URL/embed e MP4.
- Programacao por dia e horario (`TVProgramacaoItem`).
- Gestao de banners para portal.

## Apoio

- `documentos`: procuracoes e outorgados.
- `autorizacoes`: solicitacoes com aprovacao/rejeicao.
- `avaliacoes`: avaliacao e gerador de anuncios.
- `credenciais`: cofre de acessos internos.
- `notificacoes`: centro de notificacoes e webpush.
- `financiamentos`: kanban de fichas.
