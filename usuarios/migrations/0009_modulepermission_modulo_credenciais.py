from django.db import migrations, models


def copy_admin_access_to_credenciais(apps, schema_editor):
    ModulePermission = apps.get_model('usuarios', 'ModulePermission')
    for perm in ModulePermission.objects.all().only('id', 'modulo_admin_usuarios', 'modulo_credenciais'):
        if not perm.modulo_credenciais and perm.modulo_admin_usuarios:
            perm.modulo_credenciais = True
            perm.save(update_fields=['modulo_credenciais'])


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0008_modulepermission_modulo_whatsapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='modulepermission',
            name='modulo_credenciais',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(copy_admin_access_to_credenciais, migrations.RunPython.noop),
    ]
