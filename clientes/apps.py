from django.apps import AppConfig

class ClientesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clientes'

    # ADICIONE ESTA FUNÇÃO
    def ready(self):
        import clientes.signals