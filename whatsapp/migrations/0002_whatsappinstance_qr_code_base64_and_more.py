from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsappinstance',
            name='qr_code_base64',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='whatsappinstance',
            name='ultima_resposta',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
