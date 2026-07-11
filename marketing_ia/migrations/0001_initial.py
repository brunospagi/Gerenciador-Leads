import crmspagi.storage_backends
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import marketing_ia.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VeiculoAnuncio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.CharField(max_length=30, unique=True, verbose_name='ID no site')),
                ('url', models.URLField(max_length=500, verbose_name='URL do anúncio')),
                ('tipo', models.CharField(choices=[('CARRO', 'Carro'), ('MOTO', 'Moto'), ('OUTRO', 'Outro')], default='OUTRO', max_length=10)),
                ('marca', models.CharField(blank=True, max_length=100, null=True)),
                ('modelo', models.CharField(blank=True, max_length=100, null=True)),
                ('titulo', models.CharField(max_length=255, verbose_name='Título completo do anúncio')),
                ('preco', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('ano', models.CharField(blank=True, max_length=15, null=True)),
                ('km', models.CharField(blank=True, max_length=20, null=True)),
                ('cor', models.CharField(blank=True, max_length=50, null=True)),
                ('cambio', models.CharField(blank=True, max_length=50, null=True)),
                ('combustivel', models.CharField(blank=True, max_length=50, null=True)),
                ('carroceria', models.CharField(blank=True, max_length=50, null=True)),
                ('portas', models.CharField(blank=True, max_length=30, null=True)),
                ('condicoes', models.JSONField(blank=True, default=list, verbose_name='Ex: Aceita Troca, IPVA Pago')),
                ('opcionais', models.JSONField(blank=True, default=list)),
                ('descricao', models.TextField(blank=True, null=True)),
                ('foto_principal_url', models.URLField(blank=True, max_length=500, null=True)),
                ('fotos_urls', models.JSONField(blank=True, default=list, verbose_name='URLs das fotos em alta resolução')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ainda encontrado no estoque do site')),
                ('coletado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Anúncio de Veículo (raspado)',
                'verbose_name_plural': 'Anúncios de Veículos (raspados)',
                'ordering': ['-atualizado_em'],
            },
        ),
        migrations.CreateModel(
            name='PostPromocional',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('imagem', models.ImageField(storage=crmspagi.storage_backends.PublicMediaStorage(), upload_to=marketing_ia.models.get_post_upload_path, verbose_name='Imagem promocional gerada')),
                ('legenda', models.TextField(verbose_name='Legenda para redes sociais')),
                ('hashtags', models.CharField(blank=True, max_length=500, null=True)),
                ('prompt_imagem', models.TextField(blank=True, editable=False, null=True)),
                ('modelo_ia_imagem', models.CharField(blank=True, editable=False, max_length=100, null=True)),
                ('modelo_ia_texto', models.CharField(blank=True, editable=False, max_length=100, null=True)),
                ('status', models.CharField(choices=[('RASCUNHO', 'Rascunho'), ('APROVADO', 'Aprovado'), ('PUBLICADO', 'Publicado'), ('DESCARTADO', 'Descartado')], default='RASCUNHO', max_length=12)),
                ('gerado_em', models.DateTimeField(auto_now_add=True)),
                ('anuncio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='posts', to='marketing_ia.veiculoanuncio')),
                ('gerado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Post Promocional (IA)',
                'verbose_name_plural': 'Posts Promocionais (IA)',
                'ordering': ['-gerado_em'],
            },
        ),
    ]
