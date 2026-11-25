from django.apps import AppConfig


class HorariosConfig(AppConfig):
    name = 'horarios'

    def ready(self):
        from . import middleware  # noqa: F401  registra la señal user_logged_in
