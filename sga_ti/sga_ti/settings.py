import importlib.util
import os
from pathlib import Path

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

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

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
            ],
        },
    },
]

WSGI_APPLICATION = "sga_ti.wsgi.application"

SQLITE_RUTA = os.environ.get("SGA_TI_DB_PATH", str(Path.home() / "sga_ti_datos" / "sga_ti.db"))

EVIDENCIAS_RUTA = os.environ.get(
    "SGA_TI_EVIDENCIAS_PATH", str(Path.home() / "sga_ti_evidencias")
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": SQLITE_RUTA,
    }
}

AUTH_USER_MODEL = "cuentas.Usuario"

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
