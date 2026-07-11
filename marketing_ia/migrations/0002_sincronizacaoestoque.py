import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('marketing_ia', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SincronizacaoEstoque',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('OCIOSO', 'Ocioso'), ('RODANDO', 'Rodando'), ('CONCLUIDO', 'Concluído'), ('ERRO', 'Erro')], default='OCIOSO', max_length=10)),
                ('iniciado_em', models.DateTimeField(blank=True, null=True)),
                ('concluido_em', models.DateTimeField(blank=True, null=True)),
                ('resultado', models.CharField(blank=True, max_length=255, null=True)),
                ('iniciado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Sincronização de Estoque',
                'verbose_name_plural': 'Sincronizações de Estoque',
            },
        ),
    ]
