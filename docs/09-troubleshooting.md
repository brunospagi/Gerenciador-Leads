# 09 - Troubleshooting

## 1. Lead nao distribui

Sinais:
- Mensagem de "nenhum vendedor elegivel".

Checklist:
- Verificar vendedores ativos no rodizio.
- Verificar entrada/almoco/retorno no ponto.
- Verificar regras de bloqueio por horario.
- Testar redistribuicao manual para validar fila.

## 2. Dashboard sem backup

Sinais:
- Botao nao gera download.

Checklist:
- Confirmar permissao ADMIN/GERENTE.
- Verificar logs de erro no servidor.
- Rodar comando manual `gerar_backup_sistema`.
- Verificar permissao de escrita em `./backups`.

## 3. Logs de auditoria vazios

Checklist:
- Confirmar `core.audit_middleware.AuditLogMiddleware` no `MIDDLEWARE`.
- Validar que acao testada e de escrita (`POST`, `PUT`, `PATCH`, `DELETE`).
- Validar usuario autenticado.
- Confirmar migracao `core/migrations/0002_auditlog.py` aplicada.

## 4. Campo novo nao aparece em tela

Checklist:
- Confirmar migracoes aplicadas.
- Limpar cache do navegador.
- Reiniciar processo da aplicacao.

## 5. Layout de impressao com quebra

Checklist:
- Confirmar template de impressao dedicado.
- Verificar CSS de `@media print`.
- Validar aba ativa antes de `window.print()`.

## 6. Media/TV nao carrega

Checklist:
- Confirmar CSP (`media-src`) com dominio do bucket.
- Validar URL/arquivo MP4 no MinIO.
- Validar credenciais `MINIO_*`.
