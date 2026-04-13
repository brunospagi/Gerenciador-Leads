from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0009_modulepermission_modulo_credenciais'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='modulepermission',
            name='modulo_whatsapp',
        ),
    ]

