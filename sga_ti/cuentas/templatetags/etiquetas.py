from django import template

from ..permisos import puede

register = template.Library()


@register.filter
def tiene_permiso(usuario, accion):
    return puede(usuario, accion)
