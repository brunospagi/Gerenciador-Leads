# 08 - Operacao e Rotina

## Comandos essenciais

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py test
```

## Rotinas agendadas

Arquivo `crontab`:

- 03:00 `check_inactivity`
- 08:00 `check_overdue_clients`

## Entrada da aplicacao

`entrypoint.sh` executa:

1. cron
2. migrate
3. collectstatic
4. comando final (gunicorn)

## Checklist de operacao

1. backup diario de banco
2. monitoramento de logs
3. revisao de permissoes
4. validacao de webhooks e push
5. em vendas: validar aprovacao e impressao automatica da minuta

## Fluxo de Minuta (Vendas)

1. Registrar venda em `vendas_produtos`
2. Gestor aprova venda (status `APROVADO`)
3. Sistema redireciona para tela de minuta
4. Impressao e aberta automaticamente
5. Conferir rodape: usuario que gerou e horario
