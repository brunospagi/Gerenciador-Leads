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

O cron roda dentro do proprio container web (`entrypoint.sh`), controlado pela variavel
`ENABLE_CRON` (default `true`). **Se a aplicacao escalar com multiplas replicas, defina
`ENABLE_CRON=false` em todas menos uma** — caso contrario cada replica roda seu proprio
cron e os jobs (e as notificacoes que eles disparam) executam duplicados.

## Backup

### Via painel

- Acessar `/painel-admin/`.
- Acionar botao `Baixar Backup (.zip)`.

### Via comando

```bash
python manage.py gerar_backup_sistema
python manage.py gerar_backup_sistema --output-dir /caminho/customizado
```

## Auditoria

- Consultar `/painel-admin/logs-auditoria/`.
- Filtrar por usuario, modulo, metodo, severidade, resultado e periodo.
- Revisar diariamente operacoes criticas.

## Checklist operacional diario

1. Confirmar entrada de leads e distribuicao sem bloqueios indevidos.
2. Revisar leads atrasados e pipeline comercial.
3. Validar aprovacoes pendentes em vendas e ponto.
4. Revisar notificacoes e erros aparentes.

## Checklist semanal

1. Exportar relatorios principais (comercial, distribuicao, DRE).
2. Conferir integridade de backup e espaco em disco.
3. Revisar logs de auditoria e acessos administrativos.
4. Revisar permissoes por modulo.
