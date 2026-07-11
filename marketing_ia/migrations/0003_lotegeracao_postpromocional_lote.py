import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('marketing_ia', '0002_sincronizacaoestoque'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoteGeracao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('RODANDO', 'Rodando'), ('CONCLUIDO', 'Concluído'), ('ERRO', 'Erro')], default='RODANDO', max_length=10)),
                ('alvo_ids', models.JSONField(blank=True, default=list, verbose_name='IDs dos VeiculoAnuncio incluídos no lote')),
                ('total_alvo', models.PositiveIntegerField(default=0)),
                ('total_gerado', models.PositiveIntegerField(default=0)),
                ('total_falhas', models.PositiveIntegerField(default=0)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('concluido_em', models.DateTimeField(blank=True, null=True)),
                ('erro', models.CharField(blank=True, max_length=255, null=True)),
                ('iniciado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Lote de Geração',
                'verbose_name_plural': 'Lotes de Geração',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.AddField(
            model_name='postpromocional',
            name='lote',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='posts', to='marketing_ia.lotegeracao'),
        ),
    ]
