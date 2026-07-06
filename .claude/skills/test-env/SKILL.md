---
name: test-env
description: Sobe o ambiente de desenvolvimento/teste local do Gerenciador-Leads (venv, SQLite, usuários de teste) e inicia o servidor Django via preview. Use quando precisar testar uma mudança no navegador, sem precisar reconstruir o ambiente do zero.
---

# /test-env

Ambiente de teste local persistente para o Gerenciador-Leads. Objetivo: nunca mais reconstruir venv/banco/usuários do zero a cada sessão.

## O que já está montado (não recriar sem necessidade)

- **Venv**: `.venv_test/` na raiz do projeto, com as deps de `requirements.txt` instaladas. É exatamente o `runtimeExecutable` já configurado em `.claude/launch.json` (`django-dev`) — **não precisa editar launch.json nem inventar caminho de python**, ele já aponta certo.
- **Banco**: `.env` na raiz com `DB_ENGINE=sqlite` (arquivo gitignorado). Sem `SQLITE_PATH` explícito, cai no default `db.sqlite3` na raiz (também gitignorado). Esse banco é persistente entre sessões — **não apagar**.
- **Usuários de teste**: comando `python manage.py seed_test_data` (em `core/management/commands/seed_test_data.py`), idempotente, cria/atualiza 3 usuários com cadastro funcional completo (não-placeholder):
  - `admin_teste` / `teste12345` (ADMIN, superuser)
  - `gerente_teste` / `teste12345` (GERENTE)
  - `vendedor_teste` / `teste12345` (VENDEDOR)
  - Por segurança, o comando **recusa rodar** se `DB_ENGINE` não for sqlite (nunca cria essas contas de senha conhecida num banco real).

## Passos para subir o ambiente

1. Se `.venv_test/Scripts/python.exe` não existir (checar com Glob/Bash antes de recriar), montar do zero:
   ```
   python -m venv .venv_test
   .venv_test/Scripts/python.exe -m pip install -q -r requirements.txt
   ```
2. Se `.env` não existir na raiz, criar com uma linha: `DB_ENGINE=sqlite`.
3. Rodar migrations (idempotente, sempre seguro rodar de novo): `.venv_test/Scripts/python.exe manage.py migrate`
4. Rodar o seed (idempotente): `.venv_test/Scripts/python.exe manage.py seed_test_data`
5. Se mexeu em algo em `static/` ou em templates que usam `{% static %}` com nomes novos, rodar `collectstatic` (o `ManifestStaticFilesStorage` do projeto precisa do manifest atualizado, senão qualquer página com `{% static %}` quebra com 500):
   ```
   .venv_test/Scripts/python.exe manage.py collectstatic --noinput
   ```
6. Subir o servidor via preview tool: `mcp__Claude_Preview__preview_start` com `name: "django-dev"` (usa o `launch.json` já existente, porta 8010).
7. Testar no navegador via `preview_eval`/`preview_fill`/`preview_click`/`preview_screenshot`, logando com um dos usuários de teste acima.
8. Ao terminar, `preview_stop` o servidor. **Não apagar** `.venv_test/`, `.env` ou `db.sqlite3` — eles ficam para a próxima sessão.

## Erros conhecidos e como não cair neles de novo

- **`ValueError: The file 'X' could not be found` em qualquer `{% static %}`**: falta rodar `collectstatic` (o storage é `ManifestStaticFilesStorage`, exige manifest.json atualizado). Rodar o passo 5.
- **`unable to open database file`**: o `SQLITE_PATH` no `.env` está com caminho estilo Unix (`/tmp/...`) — o processo do preview roda nativo no Windows, não entende esse caminho. Usar caminho relativo simples (ou nem definir `SQLITE_PATH`, deixa cair no default `db.sqlite3` na raiz).
- **Múltiplas `<form>` na mesma página** (ex: form de logout na sidebar + form da página): ao testar submit via `preview_eval`, nunca usar `document.querySelector('form')` puro — filtrar pelo campo esperado, ex: `Array.from(document.querySelectorAll('form')).find(f => f.querySelector('#id_campo_esperado'))`.
- **Simular digitação real em campo com máscara JS** (money-mask, cpf-mask etc.): `preview_fill` seta o valor de uma vez só e não dispara a máscara caractere-a-caractere. Para reproduzir de verdade o comportamento de digitação, usar `document.execCommand('insertText', false, char)` num loop, via `preview_eval`.
