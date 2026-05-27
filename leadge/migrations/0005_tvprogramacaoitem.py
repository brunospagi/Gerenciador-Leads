from django.db import migrations, models
import crmspagi.storage_backends


class Migration(migrations.Migration):

    dependencies = [
        ('leadge', '0004_banner'),
    ]

    operations = [
        migrations.CreateModel(
            name='TVProgramacaoItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=120, verbose_name='Título da Programação')),
                ('video_url', models.URLField(blank=True, help_text='Aceita link embed de YouTube ou URL direta de mídia.', null=True, verbose_name='URL do Vídeo')),
                ('video_mp4', models.FileField(blank=True, null=True, storage=crmspagi.storage_backends.PublicMediaStorage(), upload_to='tv_videos/', verbose_name='Upload de Vídeo MP4')),
                ('manual_news_ticker', models.TextField(blank=True, help_text='Se preenchido, substitui o ticker padrão enquanto este item estiver no ar.', null=True, verbose_name='Ticker Manual do Item (Opcional)')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo?')),
                ('ordem', models.PositiveIntegerField(default=0, verbose_name='Ordem de Prioridade')),
                ('dias_semana', models.CharField(default='0,1,2,3,4,5,6', help_text='Informe os números separados por vírgula: 0=Seg, 1=Ter, 2=Qua, 3=Qui, 4=Sex, 5=Sáb, 6=Dom.', max_length=20, verbose_name='Dias da Semana')),
                ('horario_inicio', models.TimeField(blank=True, null=True, verbose_name='Horário de Início')),
                ('horario_fim', models.TimeField(blank=True, null=True, verbose_name='Horário de Fim')),
                ('data_inicio', models.DateField(blank=True, null=True, verbose_name='Data Início')),
                ('data_fim', models.DateField(blank=True, null=True, verbose_name='Data Fim')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Item da Programação de TV',
                'verbose_name_plural': 'Programação da TV',
                'ordering': ['ordem', 'id'],
            },
        ),
    ]

