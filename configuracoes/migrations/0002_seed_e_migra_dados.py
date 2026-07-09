from django.db import migrations

MODULOS = [
    ('clientes', 'Clientes e Leads', 1),
    ('vendas', 'Vendas e Serviços', 2),
    ('financiamentos', 'Financiamentos', 3),
    ('ponto', 'Controle de Ponto', 4),
    ('avaliacoes', 'Avaliações', 5),
    ('financeiro', 'Financeiro', 6),
    ('distribuicao', 'Distribuição de Leads', 7),
    ('rh', 'RH e Funcionários', 8),
    ('documentos', 'Documentos', 9),
    ('autorizacoes', 'Autorizações', 10),
    ('relatorios', 'Relatórios Gerenciais', 11),
    ('usuarios_admin', 'Acessos e Perfis', 12),
    ('credenciais', 'Credenciais e Senhas', 13),
]

# Modulos onde "excluir" hoje e mais restrito que o boolean de acesso (superuser-only
# via dispatch()), entao nao herdam pode_excluir=True automaticamente na migracao.
MODULOS_EXCLUIR_RESTRITO = {'clientes', 'avaliacoes'}

WEBHOOKS = [
    ('DISTRIBUICAO_LEADS', 'Distribuição de Leads', 'Disparado quando um novo lead é recebido/distribuído.'),
    ('CONTROLE_PONTO', 'Controle de Ponto', 'Disparado a cada nova batida de ponto registrada.'),
    ('WHATSAPP_VENDA_REJEITADA', 'WhatsApp - Venda Rejeitada', 'Disparado quando uma venda é rejeitada, para avisar vendedor e admins.'),
]

# Mapa modulo_key -> nome do campo boolean em ModulePermission (estado antes desta migracao).
MODULE_FIELD_MAP = {
    'clientes': 'modulo_clientes',
    'vendas': 'modulo_vendas',
    'financiamentos': 'modulo_financiamentos',
    'ponto': 'modulo_ponto',
    'avaliacoes': 'modulo_avaliacoes',
    'financeiro': 'modulo_financeiro',
    'distribuicao': 'modulo_distribuicao',
    'rh': 'modulo_rh',
    'documentos': 'modulo_documentos',
    'autorizacoes': 'modulo_autorizacoes',
    'relatorios': 'modulo_relatorios',
    'usuarios_admin': 'modulo_admin_usuarios',
    'credenciais': 'modulo_credenciais',
}


def seed_e_migra(apps, schema_editor):
    ModuloSistema = apps.get_model('configuracoes', 'ModuloSistema')
    PermissaoModulo = apps.get_model('configuracoes', 'PermissaoModulo')
    WebhookIntegracao = apps.get_model('configuracoes', 'WebhookIntegracao')
    ModulePermission = apps.get_model('usuarios', 'ModulePermission')

    modulos_por_slug = {}
    for slug, nome, ordem in MODULOS:
        modulo, _ = ModuloSistema.objects.get_or_create(slug=slug, defaults={'nome': nome, 'ordem': ordem})
        modulos_por_slug[slug] = modulo

    for slug, nome, descricao in WEBHOOKS:
        WebhookIntegracao.objects.get_or_create(
            slug=slug, defaults={'nome': nome, 'descricao': descricao, 'sistema': True, 'ativo': True},
        )

    for permissao_antiga in ModulePermission.objects.all():
        for slug, campo_antigo in MODULE_FIELD_MAP.items():
            tinha_acesso = bool(getattr(permissao_antiga, campo_antigo, False))
            pode_excluir = tinha_acesso and slug not in MODULOS_EXCLUIR_RESTRITO
            PermissaoModulo.objects.update_or_create(
                user_id=permissao_antiga.user_id,
                modulo=modulos_por_slug[slug],
                defaults={
                    'pode_visualizar': tinha_acesso,
                    'pode_criar': tinha_acesso,
                    'pode_editar': tinha_acesso,
                    'pode_excluir': pode_excluir,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('configuracoes', '0001_initial'),
        ('usuarios', '0010_remove_modulepermission_modulo_whatsapp'),
    ]

    operations = [
        migrations.RunPython(seed_e_migra, migrations.RunPython.noop),
    ]
