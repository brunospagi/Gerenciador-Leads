from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('controle_ponto', '0003_configuracaoponto_alter_registroponto_options'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracaoponto',
            name='horario_escala_entrada',
            field=models.TimeField(default='08:00', verbose_name='Horário Escala de Entrada'),
        ),
        migrations.AddField(
            model_name='configuracaoponto',
            name='tolerancia_atraso_minutos',
            field=models.PositiveIntegerField(default=5, verbose_name='Tolerância de Atraso (min)'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='atraso_minutos',
            field=models.PositiveIntegerField(default=0, verbose_name='Atraso na Entrada (min)'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='homologado_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Data da Homologação'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='homologado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='homologacoes_ponto', to=settings.AUTH_USER_MODEL, verbose_name='Homologado por'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='horario_escala_entrada',
            field=models.TimeField(blank=True, null=True, verbose_name='Escala de Entrada (dia)'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='justificativa_atraso',
            field=models.TextField(blank=True, null=True, verbose_name='Justificativa do Atraso'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='observacao_homologacao',
            field=models.TextField(blank=True, null=True, verbose_name='Observação da Homologação'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='status_homologacao',
            field=models.CharField(choices=[('NAO_APLICA', 'Não se aplica'), ('PENDENTE', 'Pendente de Homologação'), ('ACEITO', 'Aceito'), ('RECUSADO', 'Recusado')], default='NAO_APLICA', max_length=12, verbose_name='Status da Homologação'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='tolerancia_entrada_minutos',
            field=models.PositiveIntegerField(default=5, verbose_name='Tolerância aplicada (min)'),
        ),
    ]

