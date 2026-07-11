from django.db import migrations


def seed_modulo(apps, schema_editor):
    ModuloSistema = apps.get_model('configuracoes', 'ModuloSistema')
    ModuloSistema.objects.get_or_create(
        slug='marketing_ia', defaults={'nome': 'Marketing IA', 'ordem': 14},
    )


def remove_modulo(apps, schema_editor):
    ModuloSistema = apps.get_model('configuracoes', 'ModuloSistema')
    ModuloSistema.objects.filter(slug='marketing_ia').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('configuracoes', '0002_seed_e_migra_dados'),
        ('marketing_ia', '0004_webhook_enviowebhook'),
    ]

    operations = [
        migrations.RunPython(seed_modulo, remove_modulo),
    ]
