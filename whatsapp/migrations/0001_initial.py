import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppConversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wa_id', models.CharField(db_index=True, max_length=80, unique=True)),
                ('nome_contato', models.CharField(blank=True, max_length=180)),
                ('avatar_url', models.URLField(blank=True)),
                ('e_grupo', models.BooleanField(default=False)),
                ('ultima_mensagem', models.TextField(blank=True)),
                ('ultima_mensagem_em', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('nao_lidas', models.PositiveIntegerField(default=0)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Conversa WhatsApp',
                'verbose_name_plural': 'Conversas WhatsApp',
                'ordering': ['-ultima_mensagem_em'],
            },
        ),
        migrations.CreateModel(
            name='WhatsAppInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(default='Principal', max_length=100)),
                ('api_base_url', models.URLField()),
                ('api_key', models.CharField(max_length=255)),
                ('instance_name', models.CharField(max_length=120)),
                ('webhook_secret', models.CharField(blank=True, max_length=255, null=True)),
                ('ativo', models.BooleanField(default=True)),
                ('status_conexao', models.CharField(default='desconhecido', max_length=50)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Instancia WhatsApp',
                'verbose_name_plural': 'Instancias WhatsApp',
            },
        ),
        migrations.CreateModel(
            name='WhatsAppMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.CharField(blank=True, max_length=150, null=True, unique=True)),
                ('direcao', models.CharField(choices=[('IN', 'Recebida'), ('OUT', 'Enviada'), ('SYSTEM', 'Sistema')], max_length=10)),
                ('conteudo', models.TextField(blank=True)),
                ('media_url', models.URLField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pendente'), ('sent', 'Enviada'), ('delivered', 'Entregue'), ('read', 'Lida'), ('failed', 'Falha')], default='pending', max_length=20)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('recebido_em', models.DateTimeField(blank=True, null=True)),
                ('conversa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mensagens', to='whatsapp.whatsappconversation')),
                ('enviado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='whatsapp_mensagens_enviadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Mensagem WhatsApp',
                'verbose_name_plural': 'Mensagens WhatsApp',
                'ordering': ['criado_em'],
            },
        ),
        migrations.AddField(
            model_name='whatsappconversation',
            name='instance',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conversas', to='whatsapp.whatsappinstance'),
        ),
    ]
