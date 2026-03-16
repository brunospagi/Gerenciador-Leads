from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0007_modulepermission'),
    ]

    operations = [
        migrations.AddField(
            model_name='modulepermission',
            name='modulo_whatsapp',
            field=models.BooleanField(default=False),
        ),
    ]
