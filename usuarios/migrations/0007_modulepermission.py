from django.db import migrations, models
import django.db.models.deletion


def seed_module_permissions(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('usuarios', 'Profile')
    ModulePermission = apps.get_model('usuarios', 'ModulePermission')

    for user in User.objects.all():
        profile = Profile.objects.filter(user_id=user.id).first()
        nivel = getattr(profile, 'nivel_acesso', '')
        pode_financeiro = bool(getattr(profile, 'pode_acessar_financeiro', False))
        pode_distribuir = bool(getattr(profile, 'pode_distribuir_leads', False))

        defaults = {
            'modulo_clientes': True,
            'modulo_vendas': True,
            'modulo_financiamentos': True,
            'modulo_ponto': True,
            'modulo_avaliacoes': True,
            'modulo_financeiro': pode_financeiro,
            'modulo_distribuicao': pode_distribuir or nivel in ['ADMIN', 'GERENTE', 'DISTRIBUIDOR'],
            'modulo_rh': nivel in ['ADMIN', 'GERENTE'],
            'modulo_documentos': True,
            'modulo_autorizacoes': True,
            'modulo_relatorios': nivel in ['ADMIN', 'GERENTE'],
            'modulo_admin_usuarios': nivel == 'ADMIN',
        }

        if user.is_superuser or nivel == 'ADMIN':
            for key in defaults:
                defaults[key] = True

        ModulePermission.objects.get_or_create(user_id=user.id, defaults=defaults)


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0006_profile_pode_acessar_financeiro'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModulePermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('modulo_clientes', models.BooleanField(default=True)),
                ('modulo_vendas', models.BooleanField(default=True)),
                ('modulo_financiamentos', models.BooleanField(default=True)),
                ('modulo_ponto', models.BooleanField(default=True)),
                ('modulo_avaliacoes', models.BooleanField(default=True)),
                ('modulo_financeiro', models.BooleanField(default=False)),
                ('modulo_distribuicao', models.BooleanField(default=False)),
                ('modulo_rh', models.BooleanField(default=False)),
                ('modulo_documentos', models.BooleanField(default=False)),
                ('modulo_autorizacoes', models.BooleanField(default=False)),
                ('modulo_relatorios', models.BooleanField(default=False)),
                ('modulo_admin_usuarios', models.BooleanField(default=False)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='module_permissions', to='auth.user')),
            ],
        ),
        migrations.RunPython(seed_module_permissions, migrations.RunPython.noop),
    ]
