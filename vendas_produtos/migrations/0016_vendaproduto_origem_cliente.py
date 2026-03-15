from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vendas_produtos', '0015_alter_parametroscomissao_split_refin'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendaproduto',
            name='origem_cliente',
            field=models.CharField(
                choices=[
                    ('INDICACAO', 'Indicacao'),
                    ('INSTAGRAM', 'Instagram'),
                    ('FACEBOOK', 'Facebook'),
                    ('OLX', 'OLX'),
                    ('SITE', 'Site'),
                    ('LOJA', 'Passagem na Loja'),
                    ('WHATSAPP', 'WhatsApp'),
                    ('OUTRO', 'Outro'),
                ],
                default='OUTRO',
                max_length=20,
                verbose_name='Origem do Cliente',
            ),
        ),
    ]
