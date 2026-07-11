import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('marketing_ia', '0003_lotegeracao_postpromocional_lote'),
    ]

    operations = [
        migrations.CreateModel(
            name='Webhook',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, verbose_name='Nome do webhook')),
                ('url', models.URLField(max_length=500)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Webhook',
                'verbose_name_plural': 'Webhooks',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='EnvioWebhook',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sucesso', models.BooleanField(default=False)),
                ('status_code', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('erro', models.CharField(blank=True, max_length=255, null=True)),
                ('enviado_em', models.DateTimeField(auto_now_add=True)),
                ('enviado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='envios', to='marketing_ia.postpromocional')),
                ('webhook', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='marketing_ia.webhook')),
            ],
            options={
                'verbose_name': 'Envio de Webhook',
                'verbose_name_plural': 'Envios de Webhook',
                'ordering': ['-enviado_em'],
            },
        ),
    ]
