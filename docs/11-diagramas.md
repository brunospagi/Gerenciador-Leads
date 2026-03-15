# 11 - Diagramas

## 1. Arquitetura Geral

```mermaid
flowchart LR
    U["Usuarios (Web/PWA)"] --> DJ["Django App (crmspagi)"]
    DJ --> DB["PostgreSQL"]
    DJ --> S3["MinIO (arquivos)"]
    DJ --> WP["WebPush"]
    DJ --> OIDC["OIDC/SSO (opcional)"]
    DJ --> N8N["Webhooks (n8n)"]
```

## 2. Fluxo Comercial (Lead -> Venda -> Financeiro)

```mermaid
flowchart TD
    A["Entrada de Lead"] --> B["Distribuicao por Rodizio"]
    B --> C["Atendimento do Vendedor"]
    C --> D["Historico e Status no Cliente"]
    D --> E["Cadastro de Venda/Servico"]
    E --> F["Calculo de Comissao"]
    E --> G["Movimento Financeiro"]
    G --> H["Relatorio DRE"]
```

## 3. Controle de Acesso (Perfil + Modulo)

```mermaid
flowchart TD
    R["Requisicao do Usuario"] --> M["ModulePermissionMiddleware"]
    M --> Q{"Modulo permitido?"}
    Q -->|Nao| X["Redirect + Mensagem de Acesso Negado"]
    Q -->|Sim| V["View da Funcionalidade"]
    V --> P["Regras adicionais por Perfil (Admin/Gerente/etc)"]
    P --> Y["Resposta OK"]
```

## 4. Fluxo de Ponto e RH

```mermaid
flowchart TD
    P1["Funcionario bate ponto"] --> P2["RegistroPonto"]
    P2 --> P3["Auditoria (mapa/relatorio)"]
    P3 --> P4["FolhaPagamento"]
    P4 --> P5["Creditos/Descontos"]
    P5 --> P6["Fechamento RH"]
```

## 5. Impressao de Relatorio de Distribuicao

```mermaid
sequenceDiagram
    participant U as Usuario
    participant T as Template
    U->>T: Abre aba (Diario/Semanal/Mensal)
    U->>T: Clique em "Imprimir / PDF"
    T->>T: Define data-print-tab da aba ativa
    T->>T: Exibe print-document dedicado
    T-->>U: Documento limpo para impressao/PDF
```

## 6. Entidades Principais (Visao simplificada)

```mermaid
erDiagram
    USER ||--|| PROFILE : possui
    USER ||--|| MODULE_PERMISSION : possui
    USER ||--o{ CLIENTE : vendedor
    CLIENTE ||--o{ HISTORICO : interacoes
    USER ||--o{ VENDA_PRODUTO : vendedor
    USER ||--o{ VENDA_PRODUTO : gerente
    USER ||--o{ TRANSACAO_FINANCEIRA : criado_por
    FUNCIONARIO ||--o{ REGISTRO_PONTO : registra
```

## 7. Operacao e Rotina

```mermaid
flowchart LR
    C["Cron 03:00/08:00"] --> N["Comandos de Notificacao"]
    E["Entrypoint"] --> MG["Migrate"]
    E --> ST["Collectstatic"]
    E --> G["Gunicorn"]
    G --> APP["Aplicacao em execucao"]
```

