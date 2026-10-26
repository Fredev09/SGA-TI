from django.core.cache import cache

MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 15 * 60


def clave_intentos(request, username):
    ip = request.META.get("REMOTE_ADDR", "")
    return "intentos:%s:%s" % (ip, (username or "").strip().lower())


def fallos(request, username):
    return int(cache.get(clave_intentos(request, username)) or 0)


def esta_bloqueado(request, username):
    return fallos(request, username) >= MAX_INTENTOS


def registrar_fallo(request, username):
    clave = clave_intentos(request, username)
    total = fallos(request, username) + 1
    cache.set(clave, total, BLOQUEO_SEGUNDOS)
    return max(MAX_INTENTOS - total, 0)


def limpiar_intentos(request, username):
    cache.delete(clave_intentos(request, username))
