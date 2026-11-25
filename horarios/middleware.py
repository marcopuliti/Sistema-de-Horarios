from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.shortcuts import redirect
from django.urls import reverse

# Clave de sesión que indica que el usuario todavía usa la contraseña inicial
SESSION_DEBE_CAMBIAR_PASSWORD = 'debe_cambiar_password'


@receiver(user_logged_in)
def marcar_cambio_password(sender, request, user, **kwargs):
    """Si la contraseña es igual al email (cuenta recién creada), obliga a cambiarla."""
    if request is None or not user.email:
        return
    if user.check_password(user.email):
        request.session[SESSION_DEBE_CAMBIAR_PASSWORD] = True


class ForzarCambioPasswordMiddleware:
    """Mientras el usuario tenga la contraseña inicial, solo puede cambiarla o cerrar sesión."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.session.get(SESSION_DEBE_CAMBIAR_PASSWORD)
            and not request.path.startswith(settings.STATIC_URL)
            and request.path not in (reverse('password_change'), reverse('logout'))
        ):
            return redirect('password_change')
        return self.get_response(request)
