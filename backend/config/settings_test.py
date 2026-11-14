"""Settings para pytest: independientes del entorno del desarrollador (SQLite, DEBUG)."""

import os

os.environ["DEBUG"] = "True"
os.environ.pop("DATABASE_URL", None)

from .settings import *  # noqa: E402, F401, F403

# pytest-django ejecuta los tests con DEBUG=False: el storage con manifiesto exigiría un
# collectstatic previo para renderizar el admin. En tests basta el storage simple.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
