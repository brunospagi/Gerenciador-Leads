from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('funcionarios', '0005_funcionario_data_ultimo_dia_trabalhado'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('controle_ponto', '0006_registroponto_spagiid_auditoria'),
    ]

    operations = [
        migrations.CreateModel(
            name='FechamentoFolhaPonto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mes', models.PositiveSmallIntegerField()),
                ('ano', models.PositiveIntegerField()),
                ('fechada', models.BooleanField(default=False, verbose_name='Folha de ponto fechada?')),
                ('fechado_em', models.DateTimeField(blank=True, null=True)),
                ('observacao', models.CharField(blank=True, default='', max_length=255)),
                ('fechado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='fechamentos_folha_ponto', to=settings.AUTH_USER_MODEL)),
                ('funcionario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fechamentos_ponto', to='funcionarios.funcionario')),
            ],
            options={
                'verbose_name': 'Fechamento da Folha de Ponto',
                'verbose_name_plural': 'Fechamentos da Folha de Ponto',
                'unique_together': {('funcionario', 'mes', 'ano')},
            },
        ),
    ]
