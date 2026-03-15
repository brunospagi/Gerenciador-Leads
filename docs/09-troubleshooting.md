# 09 - Troubleshooting

## Erro de template com parenteses em `{% if %}`

Django template nao aceita parenteses em condicoes. Use condicoes expandidas com `and/or`.

## Usuario sem acesso a modulo

- verificar `usuarios/module_permissions`
- verificar perfil (`nivel_acesso`)
- verificar middleware de modulo

## Relatorio imprime pagina "quebrando layout"

- validar se template usa bloco de impressao dedicado (`print-document`)
- validar aba ativa antes de chamar `window.print()`

## Campo novo nao aparece

- confirmar migracao aplicada
- limpar cache do navegador
- reiniciar processo da aplicacao

## Coleta de estaticos

- rodar `collectstatic`
- confirmar `STATIC_ROOT` e WhiteNoise
