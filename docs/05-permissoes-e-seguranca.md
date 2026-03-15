# 05 - Permissoes e Seguranca

## Modelo de acesso

1. Perfil de usuario (`Profile.nivel_acesso`)
2. Permissao por modulo (`ModulePermission`)

## Regras tecnicas

- `usuarios/permissions.py` centraliza `has_module_access`
- `usuarios/middleware.py` bloqueia rotas por prefixo
- superuser sempre tem acesso total
- admin funcional pode ter acesso total por regra de perfil

## Modulos suportados

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

## UI de gestao

- `Usuarios -> Permissoes por Modulo`
- apenas super admin pode ver o card de permissoes no portal

## Boas praticas

- revisao mensal de acessos
- remover permissoes de usuarios inativos
- evitar conceder permissao de modulo sem necessidade
