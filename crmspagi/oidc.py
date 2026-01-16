from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from usuarios.models import Profile

class SpagiOIDCBackend(OIDCAuthenticationBackend):
    def update_user(self, user, claims):
        """
        Esta função roda SEMPRE que o usuário faz login.
        Usamos ela para sincronizar as permissões do Authentik com o Django.
        """
        # Pega a lista de grupos que vem do Authentik
        # (Certifique-se que no Authentik você configurou o envio da claim 'groups')
        roles = claims.get('groups', [])
        
        print(f"Login SSO - Usuário: {user.email} - Grupos: {roles}") # Log para debug

        # Lógica de Mapeamento de Permissões
        # Ajuste os nomes 'CRM_Admin', etc. conforme os grupos que criar no Authentik
        if 'CRM_Admin' in roles:
            user.profile.nivel_acesso = Profile.NivelAcesso.ADMIN
            user.is_staff = True      # Acesso ao painel admin do Django
            user.is_superuser = True  # Superusuário
        
        elif 'CRM_Gerente' in roles:
            user.profile.nivel_acesso = Profile.NivelAcesso.GERENTE
            user.is_staff = True      # Pode acessar admin, mas com restrições (se configurado)
            user.is_superuser = False
        
        else:
            # Se não tiver grupo especial, assume o padrão (Vendedor)
            user.profile.nivel_acesso = Profile.NivelAcesso.VENDEDOR
            user.is_staff = False
            user.is_superuser = False

        # Salva as alterações
        user.profile.save()
        user.save()

        return user

    def create_user(self, claims):
        """
        Esta função roda apenas na PRIMEIRA vez que o usuário entra.
        """
        # Cria o usuário padrão do Django
        user = super(SpagiOIDCBackend, self).create_user(claims)
        
        # O Profile é criado automaticamente pelo seu signal em models.py,
        # então aqui só chamamos o update para garantir as permissões corretas já no primeiro login.
        self.update_user(user, claims)
        
        return user