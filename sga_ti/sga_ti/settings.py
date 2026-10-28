import importlib.util
import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

_ruta_secretos = BASE_DIR / "secretos_local.py"
if _ruta_secretos.exists():
    _espec = importlib.util.spec_from_file_location("secretos_local", _ruta_secretos)
    if _espec is None or _espec.loader is None:
        raise ImproperlyConfigured("No se pudo leer sga_ti/secretos_local.py")
    _modulo = importlib.util.module_from_spec(_espec)
    _espec.loader.exec_module(_modulo)
    SECRET_KEY = _modulo.SECRET_KEY
else:
    SECRET_KEY = os.environ.get("SGA_TI_SECRET_KEY", "")
    if not SECRET_KEY:
        raise ImproperlyConfigured(
            "Falta sga_ti/secretos_local.py con la SECRET_KEY local o la variable SGA_TI_SECRET_KEY"
        )

DEBUG = os.environ.get("SGA_TI_DEBUG", "0") == "1"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("SGA_TI_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origen.strip()
    for origen in os.environ.get("SGA_TI_ORIGENES_CSRF", "").split(",")
    if origen.strip()
]

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_NUMBER_FILES = 2

if os.environ.get("SGA_TI_HTTPS") == "1":
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "cuentas",
    "ambiental",
    "operacion",
    "gestion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.CabecerasAdicionales",
]

ROOT_URLCONF = "sga_ti.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.contexto.version_estaticos",
            ],
        },
    },
]

WSGI_APPLICATION = "sga_ti.wsgi.application"

SQLITE_RUTA = os.environ.get("SGA_TI_DB_PATH", str(Path.home() / "sga_ti_datos" / "sga_ti.db"))

EVIDENCIA_MAX_MB = int(os.environ.get("SGA_TI_EVIDENCIA_MAX_MB", "1"))

EVIDENCIAS_RUTA = os.environ.get(
    "SGA_TI_EVIDENCIAS_PATH", str(Path.home() / "sga_ti_evidencias")
)

URL_BASE_DATOS = os.environ.get("SGA_TI_DATABASE_URL", "")


def _configuracion_postgres(url):
    partes = urlparse(url)
    consulta = dict(parse_qsl(partes.query))
    opciones = {}
    if consulta.get("sslmode"):
        opciones["sslmode"] = consulta["sslmode"]
    if consulta.get("channel_binding"):
        opciones["channel_binding"] = consulta["channel_binding"]
    if "-pooler" in (partes.hostname or ""):
        opciones["prepare_threshold"] = None
    opciones["connect_timeout"] = 10
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": partes.path.lstrip("/"),
        "USER": unquote(partes.username or ""),
        "PASSWORD": unquote(partes.password or ""),
        "HOST": partes.hostname or "",
        "PORT": str(partes.port or 5432),
        "OPTIONS": opciones,
    }


if URL_BASE_DATOS:
    DATABASES = {"default": _configuracion_postgres(URL_BASE_DATOS)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": SQLITE_RUTA,
        }
    }

AUTH_USER_MODEL = "cuentas.Usuario"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "sga-ti",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"

TIME_ZONE = "America/Bogota"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"

STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "cuentas:entrada"

LOGIN_REDIRECT_URL = "core:inicio"

LOGOUT_REDIRECT_URL = "cuentas:entrada"
