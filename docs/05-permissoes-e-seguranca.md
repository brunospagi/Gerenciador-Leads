# 05 - Permissoes e Seguranca

## Modelo de acesso

1. Perfil de usuario (`Profile.nivel_acesso`).
2. Permissao por modulo (`ModulePermission`).

## Controles tecnicos

- `usuarios/permissions.py`: regra central `has_module_access`.
- `usuarios/middleware.py`: bloqueio por prefixo de rota.
- Views com decorators/mixins para regras por perfil.
- Superuser com acesso total.

## Modulos controlados

- clientes
- vendas
- financiamentos
- ponto
- avaliacoes
- financeiro
- distribuicao
- rh
- documentos
- autorizacoes
- relatorios
- usuarios_admin

## Hardening e cabecalhos

- `SecurityHeadersMiddleware` aplica:
  - `Content-Security-Policy`
  - `Referrer-Policy`
  - `X-Content-Type-Options`
  - `Permissions-Policy`

## Auditoria operacional

- `AuditLogMiddleware` registra requests autenticados de escrita (`POST`, `PUT`, `PATCH`, `DELETE`).
- Dados coletados:
  - usuario e nivel
  - modulo e acao
  - rota, metodo e status HTTP
  - IP e user-agent
  - payload sanitizado (sem campos sensiveis)
- Consulta administrativa:
  - `/painel-admin/logs-auditoria/`

## Boas praticas

- Revisao mensal de acessos e perfis.
- Principio do menor privilegio por modulo.
- Revisar periodicamente logs de auditoria e eventos de erro.
- Revogar acesso de usuarios inativos imediatamente.
