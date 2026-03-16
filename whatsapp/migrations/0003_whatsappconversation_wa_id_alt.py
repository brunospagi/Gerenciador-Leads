from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0002_whatsappinstance_qr_code_base64_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsappconversation',
            name='wa_id_alt',
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
    ]
