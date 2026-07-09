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

# financeiro: List/Create usam um gate mais frouxo (AcessoFinanceiroMixin: modulo_financeiro
# OU pode_acessar_financeiro), mas Update/Delete/DRE sempre foram ADMIN-only (AcessoAdminMixin),
# independente do boolean de modulo. Nao herdar editar/excluir do boolean evita conceder de
# graca, na migracao, uma permissao que ninguem alem de ADMIN jamais teve (ADMIN continua
# tendo acesso total via bypass em has_module_action, independente do que estiver aqui).
MODULOS_EDITAR_EXCLUIR_RESTRITO = {'financeiro'}

# credenciais: List sempre foi liberado a qualquer um com modulo_credenciais=True, mas
# Create/Update/Delete sempre exigiram nivel_acesso ADMIN ou GERENTE (GestorPermissionMixin),
# independente do boolean de modulo. Sem essa restricao, um usuario VENDEDOR com acesso
# apenas de visualizacao a credenciais ganharia CRUD completo na migracao.
MODULOS_EDITAR_EXCLUIR_RESTRITO_A_GESTOR = {'credenciais'}

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
    Profile = apps.get_model('usuarios', 'Profile')

    modulos_por_slug = {}
    for slug, nome, ordem in MODULOS:
        modulo, _ = ModuloSistema.objects.get_or_create(slug=slug, defaults={'nome': nome, 'ordem': ordem})
        modulos_por_slug[slug] = modulo

    for slug, nome, descricao in WEBHOOKS:
        WebhookIntegracao.objects.get_or_create(
            slug=slug, defaults={'nome': nome, 'descricao': descricao, 'sistema': True, 'ativo': True},
        )

    niveis_gestor = {}
    for profile in Profile.objects.all().only('user_id', 'nivel_acesso'):
        niveis_gestor[profile.user_id] = profile.nivel_acesso in ('ADMIN', 'GERENTE')

    for permissao_antiga in ModulePermission.objects.all():
        e_gestor = niveis_gestor.get(permissao_antiga.user_id, False)
        for slug, campo_antigo in MODULE_FIELD_MAP.items():
            tinha_acesso = bool(getattr(permissao_antiga, campo_antigo, False))
            editar_excluir_restrito = slug in MODULOS_EDITAR_EXCLUIR_RESTRITO
            restrito_a_gestor = slug in MODULOS_EDITAR_EXCLUIR_RESTRITO_A_GESTOR and not e_gestor
            pode_editar = tinha_acesso and not editar_excluir_restrito and not restrito_a_gestor
            pode_excluir = (
                tinha_acesso
                and slug not in MODULOS_EXCLUIR_RESTRITO
                and not editar_excluir_restrito
                and not restrito_a_gestor
            )
            pode_criar = tinha_acesso and not restrito_a_gestor
            PermissaoModulo.objects.update_or_create(
                user_id=permissao_antiga.user_id,
                modulo=modulos_por_slug[slug],
                defaults={
                    'pode_visualizar': tinha_acesso,
                    'pode_criar': pode_criar,
                    'pode_editar': pode_editar,
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
