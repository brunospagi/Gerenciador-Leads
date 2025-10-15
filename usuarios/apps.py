from django.apps import AppConfig

class UsuariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usuarios'

    # ADICIONE ESTA FUNÇÃO
    def ready(self):
        import usuarios.signals