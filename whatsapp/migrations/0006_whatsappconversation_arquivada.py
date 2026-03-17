from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0005_alter_whatsappmessage_media_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsappconversation',
            name='arquivada',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]

