from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0009_cliente_evo_crm_deal_id_cliente_evo_crm_lead_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name="Email"),
        ),
    ]
