from django.apps import AppConfig

class FuncionariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'funcionarios'
    verbose_name = 'Gestão de Funcionários'

    def ready(self):
        import funcionarios.signals