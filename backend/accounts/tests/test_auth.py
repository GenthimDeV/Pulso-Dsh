import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import Profile
from accounts.permissions import IsAgent, IsRequester

User = get_user_model()
PASSWORD = "clave-de-prueba-123"


def make_user(username, role=None, **extra):
    user = User.objects.create_user(username, password=PASSWORD, **extra)
    if role:
        Profile.objects.create(user=user, role=role)
    return user


def login(client, username):
    response = client.post("/api/v1/auth/token/", {"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_login_devuelve_access_y_refresh(client):
    make_user("ana", "agent")

    assert set(login(client, "ana")) == {"access", "refresh"}


@pytest.mark.django_db
def test_login_con_clave_incorrecta_devuelve_401(client):
    make_user("ana", "agent")

    response = client.post("/api/v1/auth/token/", {"username": "ana", "password": "mala"})

    assert response.status_code == 401
    assert "access" not in response.json()


@pytest.mark.django_db
def test_login_de_usuario_inactivo_devuelve_401(client):
    make_user("ana", "agent", is_active=False)

    response = client.post("/api/v1/auth/token/", {"username": "ana", "password": PASSWORD})

    assert response.status_code == 401


@pytest.mark.django_db
def test_refresh_devuelve_un_access_valido(client):
    make_user("ana", "agent")
    tokens = login(client, "ana")

    response = client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]})

    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
    assert client.get("/api/v1/me/").status_code == 200


@pytest.mark.django_db
def test_refresh_no_acepta_un_access_token(client):
    make_user("ana", "agent")
    tokens = login(client, "ana")

    response = client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["access"]})

    assert response.status_code == 401


@pytest.mark.django_db
def test_refresh_token_no_sirve_como_access(client):
    make_user("ana", "agent")
    tokens = login(client, "ana")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['refresh']}")

    assert client.get("/api/v1/me/").status_code == 401


@pytest.mark.django_db
def test_me_sin_token_devuelve_401(client):
    assert client.get("/api/v1/me/").status_code == 401


@pytest.mark.django_db
def test_me_con_token_invalido_devuelve_401(client):
    client.credentials(HTTP_AUTHORIZATION="Bearer no-es-un-token")

    assert client.get("/api/v1/me/").status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["agent", "requester"])
def test_me_devuelve_usuario_y_rol_como_codigo(client, role):
    make_user("ana", role, first_name="Ana", last_name="Gil")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login(client, 'ana')['access']}")

    response = client.get("/api/v1/me/")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "ana"
    assert body["first_name"] == "Ana"
    assert body["role"] == role
    assert "password" not in body


@pytest.mark.django_db
def test_me_de_usuario_sin_perfil_devuelve_rol_nulo(client):
    make_user("sin.perfil")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login(client, 'sin.perfil')['access']}")

    response = client.get("/api/v1/me/")

    assert response.status_code == 200
    assert response.json()["role"] is None


@pytest.mark.django_db
def test_health_sigue_siendo_publico(client):
    assert client.get("/api/v1/health/").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("permission", "role", "expected"),
    [
        (IsAgent, "agent", True),
        (IsAgent, "requester", False),
        (IsAgent, None, False),
        (IsRequester, "requester", True),
        (IsRequester, "agent", False),
        (IsRequester, None, False),
    ],
)
def test_permisos_por_rol(permission, role, expected):
    request = APIRequestFactory().get("/")
    request.user = make_user("u", role)

    assert permission().has_permission(request, None) is expected


@pytest.mark.parametrize("permission", [IsAgent, IsRequester])
def test_permisos_por_rol_rechazan_anonimos(permission):
    request = APIRequestFactory().get("/")
    request.user = AnonymousUser()

    assert permission().has_permission(request, None) is False


@pytest.mark.django_db
def test_cors_permite_el_origen_del_frontend_y_rechaza_otros(client):
    allowed = client.get("/api/v1/health/", HTTP_ORIGIN="http://localhost:5173")
    other = client.get("/api/v1/health/", HTTP_ORIGIN="http://malo.example")

    assert allowed["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Access-Control-Allow-Origin" not in other


# --- Rotación, logout y throttling (3.5) ---


@pytest.mark.django_db
def test_refresh_rota_el_token_y_el_anterior_queda_invalido(client):
    make_user("ana", "agent")
    tokens = login(client, "ana")

    first = client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]})

    assert first.status_code == 200
    new_refresh = first.json()["refresh"]
    assert new_refresh != tokens["refresh"]
    reused = client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]})
    assert reused.status_code == 401
    assert client.post("/api/v1/auth/token/refresh/", {"refresh": new_refresh}).status_code == 200


@pytest.mark.django_db
def test_logout_invalida_el_refresh(client):
    make_user("ana", "agent")
    tokens = login(client, "ana")

    response = client.post("/api/v1/auth/logout/", {"refresh": tokens["refresh"]})

    assert response.status_code == 200
    again = client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]})
    assert again.status_code == 401


@pytest.mark.django_db
def test_logout_con_refresh_invalido_devuelve_401(client):
    response = client.post("/api/v1/auth/logout/", {"refresh": "no-es-un-token"})

    assert response.status_code == 401


@pytest.fixture
def low_rates(monkeypatch):
    """Tasas bajas y caché limpia; el contador de LocMemCache sobreviviría entre tests."""
    from django.core.cache import cache
    from rest_framework.throttling import ScopedRateThrottle

    cache.clear()
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"auth_login": "3/min", "auth_refresh": "2/min"},
    )
    yield
    cache.clear()


@pytest.mark.django_db
def test_login_se_limita_con_429_tras_superar_la_tasa(client, low_rates):
    make_user("ana", "agent")
    data = {"username": "ana", "password": "mala"}

    statuses = [client.post("/api/v1/auth/token/", data).status_code for _ in range(4)]

    assert statuses == [401, 401, 401, 429]


@pytest.mark.django_db
def test_refresh_se_limita_con_429_tras_superar_la_tasa(client, low_rates):
    statuses = [
        client.post("/api/v1/auth/token/refresh/", {"refresh": "x"}).status_code for _ in range(3)
    ]

    assert statuses == [401, 401, 429]


@pytest.mark.django_db
def test_el_throttling_de_auth_no_afecta_a_me_ni_a_health(client, low_rates):
    make_user("ana", "agent")
    tokens = login(client, "ana")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    assert all(client.get("/api/v1/me/").status_code == 200 for _ in range(6))
    assert all(client.get("/api/v1/health/").status_code == 200 for _ in range(6))
