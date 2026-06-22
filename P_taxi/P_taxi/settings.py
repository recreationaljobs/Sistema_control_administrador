"""
Django settings for P_taxi project.
"""

import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv


# =========================================================
# RUTAS PRINCIPALES
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga el archivo .env ubicado junto a manage.py.
# En Render, las variables se obtendrán desde Environment.
load_dotenv(BASE_DIR / ".env", override=True)

# Utiliza PyMySQL como controlador de MySQL.
pymysql.install_as_MySQLdb()


# =========================================================
# FUNCIONES PARA VARIABLES DE ENTORNO
# =========================================================

def env_bool(nombre, valor_predeterminado=False):
    """
    Convierte una variable de entorno en un valor booleano.
    """
    valor = os.getenv(nombre)

    if valor is None:
        return valor_predeterminado

    return valor.strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


def env_list(nombre, valor_predeterminado=""):
    """
    Convierte una variable separada por comas en una lista.
    """
    valor = os.getenv(nombre, valor_predeterminado)

    return [
        elemento.strip()
        for elemento in valor.split(",")
        if elemento.strip()
    ]


# =========================================================
# SEGURIDAD
# =========================================================

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "No se encontró SECRET_KEY en las variables de entorno."
    )


DEBUG = env_bool(
    "DEBUG",
    valor_predeterminado=False,
)


ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost",
)


# Render utiliza un proxy HTTPS.
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)


# En producción, las cookies se envían solamente por HTTPS.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG


# =========================================================
# CORS Y CSRF
# =========================================================

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
    # "https://sistema-control-administrador.onrender.com",
)


CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)


# Solo aplica CORS a las rutas de la API.
CORS_URLS_REGEX = r"^/api/.*$"


# No utilizar CORS_ALLOW_ALL_ORIGINS=True en producción.


# =========================================================
# APLICACIONES
# =========================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "django_filters",

    "App_taxi",
]


AUTH_USER_MODEL = "App_taxi.Usuario"


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # Sirve los archivos estáticos en Render.
    "whitenoise.middleware.WhiteNoiseMiddleware",

    # Debe estar antes de CommonMiddleware.
    "corsheaders.middleware.CorsMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URLS, PLANTILLAS Y SERVIDOR
# =========================================================

ROOT_URLCONF = "P_taxi.urls"


TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django.DjangoTemplates"
        ),
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                (
                    "django.template.context_processors."
                    "debug"
                ),
                (
                    "django.template.context_processors."
                    "request"
                ),
                (
                    "django.contrib.auth.context_processors."
                    "auth"
                ),
                (
                    "django.contrib.messages.context_processors."
                    "messages"
                ),
            ],
        },
    },
]


WSGI_APPLICATION = "P_taxi.wsgi.application"


# =========================================================
# BASE DE DATOS MYSQL
# =========================================================

DB_OPTIONS = {
    "charset": "utf8mb4",
}


# El certificado SSL es opcional.
# Para Aiven utiliza:
# DB_SSL_CA=P_taxi/certs/ca.pem
#
# Para MySQL local puedes dejar DB_SSL_CA vacío.
DB_SSL_CA = os.getenv("DB_SSL_CA", "").strip()

if DB_SSL_CA:
    ruta_certificado = Path(DB_SSL_CA)

    if not ruta_certificado.is_absolute():
        ruta_certificado = BASE_DIR / ruta_certificado

    if not ruta_certificado.exists():
        raise RuntimeError(
            "No se encontró el certificado SSL de MySQL en: "
            f"{ruta_certificado}"
        )

    DB_OPTIONS["ssl"] = {
        "ca": str(ruta_certificado),
    }


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", "3306"),

        "OPTIONS": DB_OPTIONS,

        # Mantiene abiertas las conexiones brevemente para mejorar
        # el rendimiento de las solicitudes consecutivas.
        "CONN_MAX_AGE": int(
            os.getenv("DB_CONN_MAX_AGE", "60")
        ),
    }
}


# =========================================================
# VALIDACIÓN DE CONTRASEÑAS
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
        "OPTIONS": {
            "min_length": 6,
        },
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =========================================================
# IDIOMA Y ZONA HORARIA
# =========================================================

LANGUAGE_CODE = "es"

TIME_ZONE = "America/Managua"

USE_I18N = True
USE_TZ = True


# =========================================================
# ARCHIVOS ESTÁTICOS
# =========================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"


STORAGES = {
    "default": {
        "BACKEND": (
            "django.core.files.storage."
            "FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}


# =========================================================
# ARCHIVOS SUBIDOS POR LOS USUARIOS
# =========================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =========================================================
# DJANGO REST FRAMEWORK
# =========================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        (
            "rest_framework.authentication."
            "TokenAuthentication"
        ),
        (
            "rest_framework.authentication."
            "SessionAuthentication"
        ),
    ],

    "DEFAULT_PERMISSION_CLASSES": [
        (
            "rest_framework.permissions."
            "IsAuthenticated"
        ),
    ],

    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],

    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],

    "DEFAULT_FILTER_BACKENDS": [
        (
            "django_filters.rest_framework."
            "DjangoFilterBackend"
        ),
    ],
}


# =========================================================
# CLAVE PRIMARIA PREDETERMINADA
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"