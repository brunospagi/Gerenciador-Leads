import re
from decimal import Decimal, InvalidOperation

from django.db import migrations, models

# Precisa bater com max_digits=12, decimal_places=2 do campo novo (10 digitos inteiros + 2 decimais).
_VALOR_MAXIMO = Decimal('9999999999.99')
_VALOR_MINIMO = -_VALOR_MAXIMO


def _parse_valor_estimado(bruto):
    """Converte texto livre (ex: 'R$ 45.000,00') para Decimal. Retorna None se nao for parseavel
    ou se o valor estourar a precisao do campo destino (dado legado invalido/lixo)."""
    if not bruto:
        return None
    limpo = re.sub(r'[^0-9,.\-]', '', bruto).strip()
    if not limpo:
        return None
    # Formato BR: ponto como separador de milhar, virgula como decimal.
    if ',' in limpo:
        limpo = limpo.replace('.', '').replace(',', '.')
    try:
        valor = Decimal(limpo)
    except (InvalidOperation, ValueError):
        return None

    if valor > _VALOR_MAXIMO or valor < _VALOR_MINIMO:
        # Dado legado invalido (ex: numero de telefone/lixo digitado no campo) nao cabe no
        # DecimalField novo. Preferimos deixar em branco a derrubar a migration inteira.
        return None

    return valor


def copiar_valor_estimado(apps, schema_editor):
    Cliente = apps.get_model('clientes', 'Cliente')
    qs = Cliente.objects.exclude(valor_estimado_veiculo_old__isnull=True).exclude(valor_estimado_veiculo_old='')
    nao_convertidos = 0
    for cliente in qs.iterator():
        valor = _parse_valor_estimado(cliente.valor_estimado_veiculo_old)
        if valor is None and cliente.valor_estimado_veiculo_old:
            nao_convertidos += 1
        cliente.valor_estimado_veiculo_novo = valor
        cliente.save(update_fields=['valor_estimado_veiculo_novo'])
    if nao_convertidos:
        print(
            f"[AVISO] {nao_convertidos} valor(es) de 'valor_estimado_veiculo' nao puderam ser "
            "convertidos automaticamente para numero (formato invalido ou fora da faixa suportada) "
            "e ficaram em branco (NULL). Revise manualmente se necessario."
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0011_alter_cliente_evo_crm_ids'),
    ]

    operations = [
        migrations.RenameField(
            model_name='cliente',
            old_name='valor_estimado_veiculo',
            new_name='valor_estimado_veiculo_old',
        ),
        migrations.AddField(
            model_name='cliente',
            name='valor_estimado_veiculo_novo',
            field=models.DecimalField(
                max_digits=12, decimal_places=2, blank=True, null=True,
                verbose_name='Valor Estimado do Veículo',
            ),
        ),
        migrations.RunPython(copiar_valor_estimado, noop_reverse),
        migrations.RemoveField(
            model_name='cliente',
            name='valor_estimado_veiculo_old',
        ),
        migrations.RenameField(
            model_name='cliente',
            old_name='valor_estimado_veiculo_novo',
            new_name='valor_estimado_veiculo',
        ),
    ]
