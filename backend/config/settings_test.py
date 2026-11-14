"""Settings para pytest: independientes del entorno del desarrollador (SQLite, DEBUG)."""

import os

os.environ["DEBUG"] = "True"
# Clave fija y larga (≥ 32 bytes): no depende del .env local ni da InsecureKeyLengthWarning.
os.environ["SECRET_KEY"] = "clave-solo-para-tests-de-pulso-0123456789"
# Tasas altas: la suite hace muchos logins desde la misma IP; los tests de throttling las bajan.
os.environ["THROTTLE_AUTH_LOGIN"] = "100000/min"
os.environ["THROTTLE_AUTH_REFRESH"] = "100000/min"
os.environ.pop("DATABASE_URL", None)

from .settings import *  # noqa: E402, F401, F403

# pytest-django ejecuta los tests con DEBUG=False: el storage con manifiesto exigiría un
# collectstatic previo para renderizar el admin. En tests basta el storage simple.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# El hash PBKDF2 por defecto domina el tiempo de la suite (cada create_user lo calcula).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
