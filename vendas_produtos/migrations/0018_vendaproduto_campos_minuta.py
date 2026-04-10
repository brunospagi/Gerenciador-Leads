from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vendas_produtos', '0017_alter_vendaproduto_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendaproduto',
            name='bairro_cliente',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Bairro'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='cep_cliente',
            field=models.CharField(blank=True, max_length=15, null=True, verbose_name='CEP'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='cidade_com_cliente',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Cidade'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='cpfCNPJ_cliente',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='CPF/CNPJ'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='data_compra',
            field=models.DateField(blank=True, null=True, verbose_name='Data de Entrada'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='documentacao_veiculo',
            field=models.TextField(blank=True, null=True, verbose_name='Documentação do Veículo'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='dtnasc_cliente',
            field=models.DateField(blank=True, null=True, verbose_name='Data Nasc.'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='endereco_cliente',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Rua'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='km_veiculo',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='KM'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='marca_veiculo',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Marca'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='numero_cliente',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Número'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='rgIE_cliente',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='RG/IE'),
        ),
        migrations.AddField(
            model_name='vendaproduto',
            name='telCel_cliente',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Celular'),
        ),
    ]
