from configuracoes.models import ServicoWebhook
from configuracoes.resolver import enviar_webhook


def _telefone_usuario(usuario):
    funcionario = getattr(usuario, 'dados_funcionais', None)
    return getattr(funcionario, 'telefone', None) if funcionario else None


def _usuario_optou_por_whatsapp(usuario):
    profile = getattr(usuario, 'profile', None)
    return profile.notificacao_whatsapp if profile else True


def notificar_whatsapp_usuario(usuario, mensagem):
    if not _usuario_optou_por_whatsapp(usuario):
        return
    telefone = _telefone_usuario(usuario)
    if not telefone:
        return
    enviar_webhook(ServicoWebhook.WHATSAPP_VENDA_REJEITADA, {"telefone": telefone, "mensagem": mensagem})


def notificar_whatsapp_venda_rejeitada(venda):
    """Notifica o vendedor da venda e todos os administradores via WhatsApp."""
    from django.contrib.auth.models import User

    from usuarios.models import Profile

    notificar_whatsapp_usuario(
        venda.vendedor,
        f"🔴 Venda Rejeitada\nCliente: {venda.cliente_nome}\nMotivo: {venda.motivo_recusa}",
    )

    mensagem_admin = (
        f"⚠️ Venda rejeitada\nVendedor: {venda.vendedor.get_full_name() or venda.vendedor.username}\n"
        f"Cliente: {venda.cliente_nome}\nMotivo: {venda.motivo_recusa}"
    )
    admins = User.objects.filter(profile__nivel_acesso=Profile.NivelAcesso.ADMIN).exclude(pk=venda.vendedor.pk)
    for admin in admins:
        notificar_whatsapp_usuario(admin, mensagem_admin)
