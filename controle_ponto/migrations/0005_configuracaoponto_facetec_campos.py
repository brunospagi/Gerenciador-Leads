from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('controle_ponto', '0004_configuracaoponto_horario_escala_entrada_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracaoponto',
            name='facetec_base_url',
            field=models.CharField(blank=True, default='', help_text='Ex.: https://api.facetec.com/api/v3.1/biometrics', max_length=255, verbose_name='FaceTec Base URL'),
        ),
        migrations.AddField(
            model_name='configuracaoponto',
            name='facetec_device_key_identifier',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='FaceTec Device Key Identifier'),
        ),
        migrations.AddField(
            model_name='configuracaoponto',
            name='facetec_habilitado',
            field=models.BooleanField(default=False, verbose_name='Habilitar validação FaceTec'),
        ),
        migrations.AddField(
            model_name='configuracaoponto',
            name='facetec_modo_producao',
            field=models.BooleanField(default=False, verbose_name='FaceTec em modo produção'),
        ),
        migrations.AddField(
            model_name='configuracaoponto',
            name='facetec_production_key',
            field=models.TextField(blank=True, default='', verbose_name='FaceTec Production Key (opcional)'),
        ),
        migrations.AddField(
            model_name='configuracaoponto',
            name='facetec_public_face_scan_encryption_key',
            field=models.TextField(blank=True, default='', verbose_name='FaceTec Public FaceScan Encryption Key'),
        ),
    ]

