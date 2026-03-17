# 14 - Diagramas das Implementacoes Recentes

## 1. Arquitetura logica do modulo WhatsApp

```mermaid
flowchart LR
    UI["Inbox (HTML/CSS/JS)"] --> V["Django Views (whatsapp/views.py)"]
    V --> S["Servicos (whatsapp/services.py)"]
    S --> EVO["Evolution API"]
    S --> DB["PostgreSQL (Conversas/Mensagens)"]
    S --> ST["Storage MinIO/default_storage"]
```

## 2. Fluxo de envio de mensagem

```mermaid
sequenceDiagram
    participant U as Usuario
    participant UI as Inbox JS
    participant V as Django View
    participant S as EvolutionAPIClient
    participant DB as Banco

    U->>UI: Envia texto/arquivo
    UI->>V: POST /whatsapp/ (action=send_message, ajax=1)
    V->>DB: Cria mensagem local (pending)
    V->>S: sendText/sendMedia/sendWhatsAppAudio
    S-->>V: response com id externo
    V->>DB: Atualiza status (sent) + external_id
    V-->>UI: JSON ok
    UI->>UI: Polling atualiza bolha/status
```

## 3. Fluxo de recebimento via webhook

```mermaid
sequenceDiagram
    participant EVO as Evolution
    participant W as WhatsAppWebhookView
    participant SV as process_webhook_payload
    participant DB as Banco
    participant UI as Inbox JS

    EVO->>W: POST /whatsapp/webhook/(event)
    W->>SV: processa evento
    SV->>DB: upsert conversa + mensagem
    SV->>DB: status/presenca/labels/reacoes
    UI->>W: GET feed/conversa/<id>/mensagens (polling)
    W-->>UI: mensagens atualizadas
```

## 4. Fluxo de status (confirmacoes)

```mermaid
flowchart TD
    A["Evento MESSAGES_UPDATE/MESSAGE_STATUS"] --> B["Extrai candidatos de message id"]
    B --> C{"Mensagem encontrada?"}
    C -->|Sim| D["Atualiza status local (sent/delivered/read/failed)"]
    C -->|Nao| E["Fallback: ultima mensagem OUT da conversa"]
    E --> F{"Encontrou fallback?"}
    F -->|Sim| D
    F -->|Nao| G["Ignora update"]
```

## 5. Fluxo de presenca (digitando/gravando)

```mermaid
flowchart TD
    A["Evento PRESENCE_UPDATE/PRESENCE_UPSERT"] --> B["Normaliza estado (typing/recording)"]
    B --> C["Resolve jid da conversa (wa_id/wa_id_alt)"]
    C --> D{"Conversa encontrada?"}
    D -->|Sim| E["Salva metadata.presence com updated_at"]
    D -->|Nao| F["Sem atualizacao"]
    E --> G["UI exibe: digitando... / gravando audio..."]
```

## 6. Fluxo de reacao

```mermaid
sequenceDiagram
    participant U as Usuario
    participant UI as Inbox JS
    participant V as react_message
    participant EVO as Evolution
    participant WH as Webhook update
    participant DB as Banco

    U->>UI: Clica em reagir
    UI->>V: POST /mensagem/<id>/reagir/
    V->>EVO: sendReaction
    EVO-->>V: OK
    V->>DB: Salva reaction_sent no payload
    EVO->>WH: webhook de reactionMessage
    WH->>DB: Atualiza reacao na mensagem alvo
    UI->>UI: Polling renderiza badge de reacao
```

## 7. Encaminhamento em lote

```mermaid
flowchart TD
    A["Seleciona mensagens"] --> B["Abre modal de contatos"]
    B --> C["Seleciona 1..N destinos"]
    C --> D["POST /mensagem/encaminhar/lote/"]
    D --> E["Reenvia texto/midia via Evolution"]
    E --> F["Cria mensagens locais de saida"]
    F --> G["Atualiza conversas e feed"]
```

## 8. Controle de acesso no portal/menu

```mermaid
flowchart TD
    U["Usuario autenticado"] --> CP["context_processors.module_access_context"]
    CP --> M["module_access por modulo"]
    M --> P["Portal (cards filtrados)"]
    M --> S["Menu lateral (itens filtrados)"]
    U --> R{"superuser?"}
    R -->|Sim| A["Mostra card/menu Permissoes por Modulo"]
    R -->|Nao| B["Oculta card/menu administrativo"]
```

## 9. ER simplificado do modulo WhatsApp

```mermaid
erDiagram
    WHATSAPP_INSTANCE {
      int id PK
      string nome
      string api_base_url
      string api_key
      string instance_name
      bool ativo
      string status_conexao
      text qr_code_base64
    }

    WHATSAPP_CONVERSATION {
      int id PK
      int instance_id FK
      string wa_id
      string wa_id_alt
      string nome_contato
      string avatar_url
      json etiquetas
      bool e_grupo
      text ultima_mensagem
      datetime ultima_mensagem_em
      int nao_lidas
      json metadata
    }

    WHATSAPP_MESSAGE {
      int id PK
      int conversa_id FK
      string external_id
      string direcao
      text conteudo
      text media_url
      string status
      int enviado_por_id FK
      json payload
      datetime criado_em
      datetime recebido_em
    }

    AUTH_USER {
      int id PK
      string username
    }

    WHATSAPP_INSTANCE ||--o{ WHATSAPP_CONVERSATION : possui
    WHATSAPP_CONVERSATION ||--o{ WHATSAPP_MESSAGE : possui
    AUTH_USER ||--o{ WHATSAPP_MESSAGE : envia
```

