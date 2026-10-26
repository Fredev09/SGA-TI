class CabecerasAdicionales:
    POLITICA = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    PERMISOS = "camera=(), microphone=(), geolocation=()"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        respuesta.headers.setdefault("Content-Security-Policy", self.POLITICA)
        respuesta.headers.setdefault("Permissions-Policy", self.PERMISOS)
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated:
            respuesta.headers.setdefault("Cache-Control", "no-store")
        return respuesta
