# 12 - Diagrama de Banco de Dados

Este diagrama representa as entidades centrais do sistema em nivel funcional.

## ER Principal

```mermaid
erDiagram
    USER {
      int id PK
      string username
      string email
      bool is_active
      bool is_superuser
    }

    PROFILE {
      int id PK
      int user_id FK
      string nivel_acesso
      bool pode_distribuir_leads
      bool pode_acessar_financeiro
    }

    MODULE_PERMISSION {
      int id PK
      int user_id FK
      bool modulo_clientes
      bool modulo_vendas
      bool modulo_financeiro
      bool modulo_distribuicao
      bool modulo_rh
      bool modulo_relatorios
      bool modulo_admin_usuarios
    }

    CLIENTE {
      int id PK
      int vendedor_id FK
      string nome_cliente
      string whatsapp
      string status_negociacao
      string status_contato
      string etapa_funil
      string prioridade
      datetime data_primeiro_contato
      datetime data_ultimo_contato
      datetime data_proximo_contato
      datetime data_ultimo_andamento
    }

    LEAD_ANDAMENTO {
      int id PK
      int cliente_id FK
      int usuario_id FK
      string status_contato
      string etapa_funil
      string proximo_passo
      datetime data_proxima_acao
      text comentario
      datetime criado_em
    }

    HISTORICO {
      int id PK
      int cliente_id FK
      datetime data_interacao
      text motivacao
    }

    VENDEDOR_RODIZIO {
      int id PK
      int vendedor_id FK
      bool ativo
      int ordem
      datetime ultima_atribuicao
    }

    VENDA_PRODUTO {
      int id PK
      int vendedor_id FK
      int gerente_id FK
      int vendedor_ajudante_id FK
      string tipo_produto
      string origem_cliente
      string status
      decimal valor_venda
      decimal custo_base
      decimal comissao_vendedor
      decimal comissao_ajudante
      decimal lucro_loja
      date data_venda
    }

    TRANSACAO_FINANCEIRA {
      int id PK
      int criado_por_id FK
      string tipo
      string categoria
      decimal valor
      date data_vencimento
      date data_pagamento
      bool efetivado
      bool recorrente
    }

    FUNCIONARIO {
      int id PK
      int user_id FK
      string nome_completo
      string cargo
      bool ativo
    }

    REGISTRO_PONTO {
      int id PK
      int funcionario_id FK
      date data
      time entrada
      time saida_almoco
      time retorno_almoco
      time saida
      string ip_registrado
    }

    FOLHA_PAGAMENTO {
      int id PK
      int funcionario_id FK
      int mes
      int ano
      decimal salario_base
      decimal total_creditos_manuais
      decimal total_descontos_manuais
      bool fechada
      bool pago
    }

    AUDIT_LOG {
      int id PK
      datetime created_at
      int user_id FK
      string username_snapshot
      string nivel_acesso_snapshot
      string module
      string action
      string method
      string path
      int status_code
      string ip_address
      bool success
      string severity
    }

    TV_VIDEO {
      int id PK
      string titulo
      string video_url
      string video_mp4
      text manual_news_ticker
      datetime last_updated
    }

    TV_PROGRAMACAO_ITEM {
      int id PK
      string titulo
      string video_url
      string video_mp4
      bool ativo
      int ordem
      string dias_semana
      time horario_inicio
      time horario_fim
      date data_inicio
      date data_fim
    }

    USER ||--|| PROFILE : possui
    USER ||--|| MODULE_PERMISSION : possui

    USER ||--o{ CLIENTE : vendedor
    CLIENTE ||--o{ HISTORICO : anotacoes
    CLIENTE ||--o{ LEAD_ANDAMENTO : timeline
    USER ||--o{ LEAD_ANDAMENTO : registra

    USER ||--o{ VENDEDOR_RODIZIO : participa

    USER ||--o{ VENDA_PRODUTO : vendedor
    USER ||--o{ VENDA_PRODUTO : gerente
    USER ||--o{ VENDA_PRODUTO : ajudante

    USER ||--o{ TRANSACAO_FINANCEIRA : criou

    USER ||--|| FUNCIONARIO : colaborador
    FUNCIONARIO ||--o{ REGISTRO_PONTO : registros
    FUNCIONARIO ||--o{ FOLHA_PAGAMENTO : folhas

    USER ||--o{ AUDIT_LOG : gera
```

## Observacoes

- O diagrama e funcional e nao lista todos os campos tecnicos de cada app.
- Entidades centrais para BI comercial: `CLIENTE`, `LEAD_ANDAMENTO`, `VENDA_PRODUTO`.
- Entidades centrais para financeiro e RH: `TRANSACAO_FINANCEIRA`, `REGISTRO_PONTO`, `FOLHA_PAGAMENTO`.
- Entidade de governanca: `AUDIT_LOG`.
