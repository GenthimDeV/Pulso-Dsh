import pytest
from django.db import connection
from rest_framework.test import APIClient

URL = "/api/v1/health/"


@pytest.mark.django_db
def test_health_ok():
    response = APIClient().get(URL)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_sin_bd_devuelve_503(monkeypatch):
    def broken_cursor(*args, **kwargs):
        from django.db.utils import OperationalError

        raise OperationalError("BD caída")

    monkeypatch.setattr(connection, "cursor", broken_cursor)

    response = APIClient().get(URL)

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "error"}
