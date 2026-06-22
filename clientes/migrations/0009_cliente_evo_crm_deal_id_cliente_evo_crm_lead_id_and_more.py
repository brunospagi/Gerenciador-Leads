from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0008_cliente_etapa_funil_cliente_status_contato_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="evo_crm_deal_id",
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name="Deal ID Evo CRM"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="evo_crm_lead_id",
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name="Lead ID Evo CRM"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="evo_crm_pipeline_id",
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name="Pipeline ID Evo CRM"),
        ),
    ]
