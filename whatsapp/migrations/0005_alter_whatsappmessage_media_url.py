from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0004_whatsappconversation_etiquetas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='whatsappmessage',
            name='media_url',
            field=models.TextField(blank=True),
        ),
    ]
