from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('avaliacoes', '0003_avaliacao_tipo_veiculo'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracaoIA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(default='GEMINI', editable=False, max_length=20, verbose_name='Provedor')),
                ('modelo', models.CharField(default='gemini-2.5-flash', help_text='Ex.: gemini-2.5-flash', max_length=100, verbose_name='Modelo')),
                ('api_key', models.CharField(blank=True, help_text='Se vazio, usa GEMINI_API_KEY do .env', max_length=255, null=True, verbose_name='API Key')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'Configuração de IA',
                'verbose_name_plural': 'Configurações de IA',
            },
        ),
    ]
