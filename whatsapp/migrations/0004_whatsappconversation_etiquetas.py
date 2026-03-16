from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0003_whatsappconversation_wa_id_alt'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsappconversation',
            name='etiquetas',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
