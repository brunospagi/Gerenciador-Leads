from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('funcionarios', '0004_alter_funcionario_foto_biometria'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='data_ultimo_dia_trabalhado',
            field=models.DateField(
                blank=True,
                help_text='Preencha quando o colaborador for marcado como inativo.',
                null=True,
                verbose_name='Último dia trabalhado',
            ),
        ),
    ]

