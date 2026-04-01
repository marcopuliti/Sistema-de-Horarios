from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser or request.user.groups.filter(name='admin').exists():
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("No tenés permisos para acceder a esta sección.")
    return wrapper


def editor_or_admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if (
            request.user.is_superuser
            or request.user.groups.filter(name__in=['admin', 'editor', 'manager']).exists()
        ):
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("No tenés permisos para acceder a esta sección.")
    return wrapper


def manager_or_admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if (
            request.user.is_superuser
            or request.user.groups.filter(name__in=['admin', 'manager']).exists()
        ):
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("No tenés permisos para acceder a esta sección.")
    return wrapper


def is_admin(user):
    return user.is_superuser or user.groups.filter(name='admin').exists()


def is_manager_or_admin(user):
    return user.is_superuser or user.groups.filter(name__in=['admin', 'manager']).exists()


def is_editor(user):
    return user.groups.filter(name='editor').exists()
