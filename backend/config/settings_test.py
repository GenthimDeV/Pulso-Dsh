"""Settings para pytest: independientes del entorno del desarrollador (SQLite, DEBUG)."""

import os

os.environ["DEBUG"] = "True"
os.environ.pop("DATABASE_URL", None)

from .settings import *  # noqa: E402, F401, F403
