from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0010_remove_modulepermission_modulo_whatsapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='modulepermission',
            name='modulo_marketing_ia',
            field=models.BooleanField(default=False),
        ),
    ]
