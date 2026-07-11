from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configuracoes', '0002_seed_e_migra_dados'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracaointegracoes',
            name='provedor_imagem_ia',
            field=models.CharField(
                choices=[('GEMINI', 'Gemini (Google)'), ('LEONARDO', 'Leonardo.Ai')],
                default='GEMINI',
                max_length=20,
                verbose_name='Provedor de geração de imagem (Marketing IA)',
            ),
        ),
        migrations.AddField(
            model_name='configuracaointegracoes',
            name='leonardo_api_key',
            field=models.CharField(blank=True, max_length=255, verbose_name='Leonardo.Ai - Chave da API'),
        ),
    ]
