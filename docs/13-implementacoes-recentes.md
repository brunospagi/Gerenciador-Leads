# 13 - Implementacoes Recentes (WhatsApp, Permissoes e Relatorios)

Este documento consolida as implementacoes mais recentes realizadas no CRM.

## 1. Escopo consolidado

### 1.1 Permissoes e controle de acesso
- Controle por modulo no portal e menu lateral via `module_access`.
- Tela de permissao por modulo para administracao de usuarios.
- Exibicao da opcao "Permissoes por Modulo" apenas para `superuser` no portal/menu.
- Restricoes adicionais por perfil (`ADMIN`, `GERENTE`, etc.) em pontos sensiveis.

Arquivos base:
- `crmspagi/templates/base_portal.html`
- `crmspagi/templates/portal.html`
- `usuarios/context_processors.py`
- `usuarios/permissions.py`
- `usuarios/views.py`

### 1.2 Relatorio de distribuicao (impressao/PDF)
- Ajuste para impressao limpa sem renderizar a pagina inteira.
- Template dedicado para impressao.
- Controle de aba ativa (diario/semanal/mensal) no print.

Arquivos base:
- `distribuicao/views.py`
- `distribuicao/templates/distribuicao/relatorio_distribuicao.html`
- `distribuicao/templates/distribuicao/relatorio_distribuicao_print.html`

### 1.3 Modulo WhatsApp (Central WhatsApp)
- Inbox estilo WhatsApp Web com lista de conversas e chat em tempo real.
- Configuracao de instancia com criacao/conexao e QR Code.
- Webhook com suporte para eventos de mensagem, status, presenca, etiquetas e conexao.
- Polling AJAX para conversas e mensagens.
- Encaminhamento individual e em lote com seletor de contatos.
- Reacao em mensagens.
- Suporte a imagem, video, audio, documento e figurinha.
- Upload/recebimento de midia com persistencia (MinIO/storage).
- Tratamento de `@lid` + `wa_id_alt` para evitar duplicidade de conversa.
- Normalizacao de URLs de midia relativas (ex.: `/o1/...`) para URL publica.
- Indicacao de presenca (`digitando`, `gravando audio`) por webhook.

Arquivos base:
- `whatsapp/models.py`
- `whatsapp/views.py`
- `whatsapp/services.py`
- `whatsapp/urls.py`
- `whatsapp/templates/whatsapp/inbox.html`
- `whatsapp/static/whatsapp/inbox.css`
- `whatsapp/static/whatsapp/inbox.js`

## 2. Endpoints importantes do modulo WhatsApp

Base: `/whatsapp/`

- `GET /` -> Inbox.
- `GET /feed/conversas/` -> Feed AJAX de conversas.
- `GET /feed/conversa/<id>/mensagens/` -> Feed AJAX de mensagens.
- `POST /mensagem/<id>/reagir/` -> Envio de reacao.
- `POST /mensagem/<id>/encaminhar/` -> Encaminhamento individual.
- `POST /mensagem/encaminhar/lote/` -> Encaminhamento em lote.
- `POST /conversa/<id>/marcar-lida/` -> Marca conversa como lida.
- `POST /conversa/<id>/deletar/` -> Remove conversa.
- `GET|POST /instancia/` -> Configuracao da instancia.
- `GET /instancia/<id>/status/` -> Status em runtime.
- `POST /webhook/` e variantes por evento -> Recepcao de eventos da Evolution.

## 3. Eventos de webhook tratados

- `MESSAGES_UPSERT` (mensagens novas).
- `MESSAGES_UPDATE`, `MESSAGE_UPDATE` (atualizacao de conteudo/status/reacao).
- `MESSAGE_STATUS`, `SEND_MESSAGE` (confirmacoes de entrega/leitura).
- `PRESENCE_UPDATE`, `PRESENCE_UPSERT` (digitando/gravando).
- `LABELS_ASSOCIATION`, `LABELS_EDIT`, `CONTACTS_UPDATE` (etiquetas e contatos).
- `CONNECTION_UPDATE`, `CONNECTION_STATE` (estado da instancia).
- `QRCODE_UPDATED` (atualizacao de QR code).

## 4. Banco de dados (impacto funcional)

### 4.1 Tabelas principais do modulo
- `WhatsAppInstance`
- `WhatsAppConversation`
- `WhatsAppMessage`

### 4.2 Campos de destaque
- `WhatsAppConversation.wa_id_alt` para suporte a identificadores `@lid`.
- `WhatsAppMessage.external_id` para correlacionar updates/status com mensagem local.
- `WhatsAppMessage.payload` para armazenar metadados de webhook, reacoes e updates.

## 5. Fluxos AJAX no front

- Busca de conversa sem reload (debounce + `history.replaceState`).
- Atualizacao automatica de lista de conversas e painel de mensagens.
- Acoes por AJAX:
  - enviar mensagem
  - marcar lida
  - deletar conversa
  - reagir
  - encaminhar

## 6. Boas praticas adotadas

- Normalizacao centralizada de JIDs e IDs externos.
- Fallback para updates sem `message id` explicito.
- Suporte a payloads heterogeneos da Evolution (dict/list e variacoes de chave).
- Separacao de responsabilidades:
  - `services.py` para integracao/processamento
  - `views.py` para camada HTTP
  - `inbox.js` para UX em tempo real

## 7. Itens de monitoramento continuo

- Validar em homologacao/producao todos os formatos de webhook da instancia ativa.
- Monitorar taxa de eventos de presenca para evitar ruido excessivo.
- Revisar periodicamente `payload` salvo para crescimento de dados.
- Avaliar futuro canal push (WebSocket/SSE) para reduzir polling.

## 8. Checklist de deploy

- Aplicar migracoes pendentes (`manage.py migrate`).
- Recoletar estaticos (`manage.py collectstatic`).
- Confirmar variaveis da Evolution API e storage.
- Garantir webhook configurado para os eventos suportados.
- Validar fluxo ponta a ponta:
  - conexao de instancia
  - envio de texto/midia
  - recebimento de midia
  - status de entrega/leitura
  - presenca e reacoes

