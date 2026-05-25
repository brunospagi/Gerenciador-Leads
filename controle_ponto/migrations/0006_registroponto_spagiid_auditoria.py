from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('controle_ponto', '0005_configuracaoponto_facetec_campos'),
    ]

    operations = [
        migrations.AddField(
            model_name='registroponto',
            name='face_distance',
            field=models.FloatField(
                blank=True,
                help_text='Menor é melhor; representa divergência da foto de cadastro.',
                null=True,
                verbose_name='Distância Facial',
            ),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='face_match_aprovado',
            field=models.BooleanField(default=False, verbose_name='Face Match Aprovado'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='face_threshold',
            field=models.FloatField(blank=True, null=True, verbose_name='Limite de Distância Facial'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='face_validado_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Data/Hora da Validação Facial'),
        ),
        migrations.AddField(
            model_name='registroponto',
            name='modo_validacao',
            field=models.CharField(
                blank=True,
                help_text='Ex.: biometria, manual_foto_estatica',
                max_length=30,
                null=True,
                verbose_name='Modo de Validação',
            ),
        ),
    ]

