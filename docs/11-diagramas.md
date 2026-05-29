# 11 - Diagramas

## 1. Arquitetura Geral

```mermaid
flowchart LR
    U[Usuarios Web PWA] --> DJ[Django crmspagi]
    DJ --> DB[(PostgreSQL ou SQLite)]
    DJ --> S3[(MinIO media)]
    DJ --> WS[WebPush]
    DJ --> OIDC[OIDC opcional]
    DJ --> N8N[Webhook n8n]
```

## 2. Fluxo Comercial Lead ate Venda

```mermaid
flowchart TD
    A[Entrada de Lead] --> B[Distribuicao por Rodizio]
    B --> C[Vendedor Responsavel]
    C --> D[Painel Comercial do Lead]
    D --> E[Andamentos Timeline]
    E --> F{Converteu}
    F -->|Sim| G[Cadastro de Venda Servico]
    F -->|Nao| H[Follow up ou Encerramento]
    G --> I[Comissao]
    G --> J[Financeiro DRE]
```

## 3. Regras de Acesso

```mermaid
flowchart TD
    R[Request] --> M[ModulePermissionMiddleware]
    M --> Q{Modulo permitido}
    Q -->|Nao| X[Redirect com mensagem]
    Q -->|Sim| V[View]
    V --> P[Validacao por perfil]
    P --> Y[Resposta]
```

## 4. Auditoria de Escrita

```mermaid
flowchart TD
    A[Usuario autenticado] --> B[Requisicao POST PUT PATCH DELETE]
    B --> C[AuditLogMiddleware]
    C --> D[Sanitiza payload]
    D --> E[(AuditLog)]
    E --> F[Painel logs auditoria]
```

## 5. Backup Operacional

```mermaid
flowchart TD
    A[Admin Gerente] --> B{Origem da acao}
    B -->|Painel| C[/painel-admin/backup/]
    B -->|CLI| D[manage.py gerar_backup_sistema]
    C --> E[create_system_backup]
    D --> E
    E --> F[dumpdata JSON]
    E --> G[copia media local se existir]
    E --> H[metadata restore notes]
    F --> I[zip final]
    G --> I
    H --> I
```

## 6. Fluxo Ponto e Folha

```mermaid
flowchart TD
    A[Registro de ponto] --> B[Homologacao admin]
    B --> C[Consolidacao RH]
    C --> D[Calculo folha]
    D --> E[Holerite detalhado]
    E --> F[Hash de integridade no rodape]
```

## 7. TV Corporativa

```mermaid
flowchart LR
    A[Gestao TV] --> B[TVProgramacaoItem]
    A --> C[TVVideo fallback]
    B --> D[tv-video exibicao]
    C --> D
    D --> E[Ticker manual ou API noticias]
```
